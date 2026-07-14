from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from planning.roadmap_registry import (
    ProjectNotFoundError,
    ProjectStatusTransitionError,
    RoadmapSnapshotConflictError,
    SQLiteRoadmapSnapshotRegistry,
    StoredRoadmapSnapshot,
    create_stored_roadmap_snapshot,
)
from planning.roadmap_snapshot import (
    build_roadmap_snapshot,
)
from schemas.product_models import RoadmapStage


CREATED_AT = datetime(
    2026,
    7,
    13,
    12,
    0,
    tzinfo=timezone.utc,
)


def _snapshot(
    *,
    purpose: str = "Build the MVP.",
):
    return build_roadmap_snapshot(
        [
            RoadmapStage(
                id="mvp",
                title="Build MVP",
                purpose=purpose,
                tasks=[
                    "Implement the first working flow."
                ],
            ),
            RoadmapStage(
                id="validate",
                title="Validate behavior",
                purpose="Measure expected behavior.",
                tasks=[
                    "Run deterministic validation."
                ],
            ),
        ]
    )


def _record(
    *,
    project_direction_id: str = (
        "project-direction-one"
    ),
    purpose: str = "Build the MVP.",
    supersedes_id: str | None = None,
) -> StoredRoadmapSnapshot:
    return StoredRoadmapSnapshot(
        project_direction_id=(
            project_direction_id
        ),
        response_direction_id="direction-1",
        title="Evidence Attribution Engine",
        snapshot=_snapshot(purpose=purpose),
        created_at=CREATED_AT,
        supersedes_id=supersedes_id,
    )


def test_factory_creates_opaque_registry_identities():
    record = create_stored_roadmap_snapshot(
        response_direction_id="direction-1",
        title="Evidence Attribution Engine",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )

    assert record.project_id is not None
    assert record.project_id.startswith("proj_")
    assert record.roadmap_snapshot_id is not None
    assert record.roadmap_snapshot_id.startswith(
        "snap_"
    )
    assert record.project_direction_id
    assert (
        record.project_direction_id
        != record.response_direction_id
    )
    assert len(record.project_direction_id) == 36


def test_sqlite_registry_persists_across_instances(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    record = _record()

    saved = SQLiteRoadmapSnapshotRegistry(
        database_path
    ).create(record)

    loaded = SQLiteRoadmapSnapshotRegistry(
        database_path
    ).load(record.project_direction_id)

    assert loaded == saved
    assert loaded is not saved
    assert loaded is not None
    assert (
        loaded.snapshot.roadmap_hash
        == record.snapshot.roadmap_hash
    )


def test_exact_duplicate_create_is_idempotent(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    record = _record()

    first = registry.create(record)
    second = registry.create(record)

    assert second == first
    assert len(registry.list_snapshots()) == 1


def test_project_direction_id_is_immutable(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    registry.create(_record())

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="different immutable",
    ):
        registry.create(
            _record(
                purpose=(
                    "Build a materially changed MVP."
                )
            )
        )

    loaded = registry.load(
        "project-direction-one"
    )

    assert loaded is not None
    assert (
        loaded.snapshot
        == _record().snapshot
    )


def test_registry_isolates_workspaces(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    first = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-one",
    )
    second = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-two",
    )

    first.create(_record())

    assert first.load(
        "project-direction-one"
    ) is not None
    assert second.load(
        "project-direction-one"
    ) is None
    assert second.list_snapshots() == []


def test_registry_lists_newest_snapshots_first(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    first = _record(
        project_direction_id="first"
    )
    second = _record(
        project_direction_id="second"
    ).model_copy(
        update={
            "created_at": datetime(
                2026,
                7,
                14,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        },
        deep=True,
    )

    registry.create(first)
    registry.create(second)

    assert [
        record.project_direction_id
        for record in registry.list_snapshots()
    ] == [
        "second",
        "first",
    ]


def test_supersession_requires_same_workspace_record(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="does not exist in this workspace",
    ):
        registry.create(
            _record(
                project_direction_id="replacement",
                supersedes_id="missing",
            )
        )


def test_create_many_persists_batch_atomically(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    records = [
        _record(
            project_direction_id="direction-record-one"
        ),
        _record(
            project_direction_id="direction-record-two"
        ),
        _record(
            project_direction_id="direction-record-three"
        ),
    ]

    saved = registry.create_many(records)

    assert [
        record.project_direction_id
        for record in saved
    ] == [
        record.project_direction_id
        for record in records
    ]
    assert all(
        record.project_id is not None
        for record in saved
    )
    assert all(
        record.roadmap_snapshot_id is not None
        for record in saved
    )
    assert {
        record.project_direction_id
        for record in registry.list_snapshots()
    } == {
        "direction-record-one",
        "direction-record-two",
        "direction-record-three",
    }


def test_create_many_rolls_back_entire_batch_on_conflict(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    existing = _record(
        project_direction_id="existing"
    )
    saved_existing = registry.create(existing)

    valid_new_record = _record(
        project_direction_id="new-record"
    )
    conflicting_record = _record(
        project_direction_id="existing",
        purpose="Changed immutable roadmap content.",
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="different immutable",
    ):
        registry.create_many(
            [
                valid_new_record,
                conflicting_record,
            ]
        )

    assert registry.load("new-record") is None
    assert (
        registry.load("existing")
        == saved_existing
    )


def test_create_many_rejects_duplicate_ids_before_writing(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="duplicate project direction IDs",
    ):
        registry.create_many(
            [
                _record(
                    project_direction_id="duplicate"
                ),
                _record(
                    project_direction_id="duplicate"
                ),
            ]
        )

    assert registry.list_snapshots() == []


def test_create_many_is_idempotent_for_exact_batch(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    records = [
        _record(project_direction_id="first-batch"),
        _record(project_direction_id="second-batch"),
    ]

    first = registry.create_many(records)
    second = registry.create_many(records)

    assert second == first
    assert len(registry.list_snapshots()) == 2


def test_registry_persists_project_and_snapshot_identity(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    registry = SQLiteRoadmapSnapshotRegistry(
        database_path
    )

    record = create_stored_roadmap_snapshot(
        response_direction_id="direction-1",
        title="Evidence Attribution Engine",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )

    saved = registry.create(record)
    loaded = registry.load(
        record.project_direction_id
    )

    assert loaded == saved
    assert loaded is not None
    assert loaded.project_id == record.project_id
    assert (
        loaded.roadmap_snapshot_id
        == record.roadmap_snapshot_id
    )

    import sqlite3

    connection = sqlite3.connect(
        str(database_path)
    )
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            """
            SELECT
                project.project_id,
                roadmap.roadmap_snapshot_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE roadmap.project_direction_id = ?
            """,
            (record.project_direction_id,),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row["project_id"] == record.project_id
    assert (
        row["roadmap_snapshot_id"]
        == record.roadmap_snapshot_id
    )


def test_registry_reuses_explicit_project_identity(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    first = create_stored_roadmap_snapshot(
        project_id="proj_shared",
        response_direction_id="direction-1",
        title="Shared project",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )
    second = create_stored_roadmap_snapshot(
        project_id="proj_shared",
        response_direction_id="direction-2",
        title="Shared project",
        snapshot=_snapshot(
            purpose="Build the second roadmap."
        ),
        created_at=CREATED_AT,
    )

    saved = registry.create_many(
        [first, second]
    )

    assert {
        record.project_id
        for record in saved
    } == {"proj_shared"}
    assert len(
        {
            record.roadmap_snapshot_id
            for record in saved
        }
    ) == 2


def test_registry_backfills_manual_record_identity(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    record = _record()

    saved = registry.create(record)

    assert saved.project_id == (
        "proj_migrated_project-direction-one"
    )
    assert saved.roadmap_snapshot_id == (
        "snap_migrated_project-direction-one"
    )

    loaded = registry.load(
        record.project_direction_id
    )

    assert loaded == saved


def _durable_record() -> StoredRoadmapSnapshot:
    return StoredRoadmapSnapshot(
        project_id="proj_one",
        roadmap_snapshot_id="snap_one",
        project_direction_id="direction-one",
        response_direction_id="direction-one",
        title="Durable roadmap",
        snapshot=_snapshot(
            purpose="Build the MVP."
        ),
        created_at=CREATED_AT,
    )


def test_registry_loads_same_record_by_all_identities(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(_durable_record())

    assert (
        registry.load(
            stored.project_direction_id
        )
        == stored
    )
    assert (
        registry.load_by_snapshot_id(
            stored.roadmap_snapshot_id
        )
        == stored
    )
    assert (
        registry.load_by_durable_identity(
            project_id=stored.project_id,
            roadmap_snapshot_id=(
                stored.roadmap_snapshot_id
            ),
        )
        == stored
    )


def test_registry_rejects_wrong_project_for_snapshot(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(_durable_record())

    assert (
        registry.load_by_durable_identity(
            project_id="proj_wrong",
            roadmap_snapshot_id=(
                stored.roadmap_snapshot_id
            ),
        )
        is None
    )


def test_registry_durable_lookup_is_workspace_isolated(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    first = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-one",
    )
    second = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-two",
    )

    stored = first.create(_durable_record())

    assert (
        second.load_by_snapshot_id(
            stored.roadmap_snapshot_id
        )
        is None
    )
    assert (
        second.load_by_durable_identity(
            project_id=stored.project_id,
            roadmap_snapshot_id=(
                stored.roadmap_snapshot_id
            ),
        )
        is None
    )



def test_supersession_requires_same_durable_project(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    predecessor = create_stored_roadmap_snapshot(
        project_id="proj_one",
        response_direction_id="direction-one",
        title="First project",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )
    stored_predecessor = registry.create(predecessor)

    replacement = create_stored_roadmap_snapshot(
        project_id="proj_two",
        response_direction_id="direction-two",
        title="Second project",
        snapshot=_snapshot(
            purpose="Build another project."
        ),
        created_at=CREATED_AT,
        supersedes_id=(
            stored_predecessor.project_direction_id
        ),
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="same durable project",
    ):
        registry.create(replacement)

    assert registry.load(
        stored_predecessor.project_direction_id
    ) == stored_predecessor
    assert registry.load(
        replacement.project_direction_id
    ) is None


def test_supersession_accepts_same_durable_project(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    predecessor = create_stored_roadmap_snapshot(
        project_id="proj_shared",
        response_direction_id="direction-one",
        title="Shared project",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
    )
    stored_predecessor = registry.create(predecessor)

    replacement = create_stored_roadmap_snapshot(
        project_id="proj_shared",
        response_direction_id="direction-two",
        title="Shared project",
        snapshot=_snapshot(
            purpose="Build the replacement roadmap."
        ),
        created_at=CREATED_AT,
        supersedes_id=(
            stored_predecessor.project_direction_id
        ),
    )

    stored_replacement = registry.create(replacement)

    assert (
        stored_replacement.supersedes_id
        == stored_predecessor.project_direction_id
    )
    assert (
        stored_replacement.project_id
        == stored_predecessor.project_id
        == "proj_shared"
    )
    assert registry.load(
        stored_predecessor.project_direction_id
    ) == stored_predecessor


def test_cross_project_supersession_rolls_back_batch(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    predecessor = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_one",
            response_direction_id="direction-one",
            title="First project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    valid = create_stored_roadmap_snapshot(
        project_id="proj_three",
        response_direction_id="direction-three",
        title="Third project",
        snapshot=_snapshot(
            purpose="Build a valid independent roadmap."
        ),
        created_at=CREATED_AT,
    )
    invalid = create_stored_roadmap_snapshot(
        project_id="proj_two",
        response_direction_id="direction-two",
        title="Second project",
        snapshot=_snapshot(
            purpose="Build an invalid replacement."
        ),
        created_at=CREATED_AT,
        supersedes_id=predecessor.project_direction_id,
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match="same durable project",
    ):
        registry.create_many([valid, invalid])

    assert registry.load(
        valid.project_direction_id
    ) is None
    assert registry.load(
        invalid.project_direction_id
    ) is None
    assert registry.load(
        predecessor.project_direction_id
    ) == predecessor



@pytest.mark.parametrize(
    "project_status",
    ["archived", "deleted"],
)
def test_registry_reads_inactive_project_history(
    tmp_path: Path,
    project_status: str,
):
    database_path = tmp_path / "solvyn.db"
    registry = SQLiteRoadmapSnapshotRegistry(
        database_path
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_lifecycle",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    import sqlite3

    connection = sqlite3.connect(
        str(database_path)
    )
    try:
        connection.execute(
            """
            UPDATE projects
            SET status = ?
            WHERE project_id = ?
            """,
            (
                project_status,
                stored.project_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    by_direction = registry.load(
        stored.project_direction_id
    )
    by_snapshot = registry.load_by_snapshot_id(
        stored.roadmap_snapshot_id
    )
    by_identity = registry.load_by_durable_identity(
        project_id=stored.project_id,
        roadmap_snapshot_id=(
            stored.roadmap_snapshot_id
        ),
    )
    listed = registry.list_snapshots()

    assert by_direction is not None
    assert by_snapshot is not None
    assert by_identity is not None
    assert by_direction.project_status == project_status
    assert by_snapshot.project_status == project_status
    assert by_identity.project_status == project_status
    assert listed[0].project_status == project_status


@pytest.mark.parametrize(
    "project_status",
    ["archived", "deleted"],
)
def test_registry_rejects_new_snapshot_for_inactive_project(
    tmp_path: Path,
    project_status: str,
):
    database_path = tmp_path / "solvyn.db"
    registry = SQLiteRoadmapSnapshotRegistry(
        database_path
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_lifecycle",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    import sqlite3

    connection = sqlite3.connect(
        str(database_path)
    )
    try:
        connection.execute(
            """
            UPDATE projects
            SET status = ?
            WHERE project_id = ?
            """,
            (
                project_status,
                stored.project_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    replacement = create_stored_roadmap_snapshot(
        project_id=stored.project_id,
        response_direction_id="direction-two",
        title="Lifecycle project",
        snapshot=_snapshot(
            purpose="Build another roadmap."
        ),
        created_at=CREATED_AT,
    )

    with pytest.raises(
        RoadmapSnapshotConflictError,
        match=(
            f"Cannot create a roadmap snapshot "
            f"for a {project_status} project"
        ),
    ):
        registry.create(replacement)

    historical = registry.load(
        stored.project_direction_id
    )

    assert historical is not None
    assert historical.project_status == project_status
    assert registry.load(
        replacement.project_direction_id
    ) is None



def test_project_status_transition_is_audited(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )
    changed_at = datetime(
        2026,
        7,
        14,
        15,
        0,
        tzinfo=timezone.utc,
    )

    transition = registry.transition_project_status(
        stored.project_id,
        new_status="archived",
        changed_at=changed_at,
        reason="Project paused.",
    )

    assert transition is not None
    assert transition.project_id == stored.project_id
    assert transition.previous_status == "active"
    assert transition.new_status == "archived"
    assert transition.changed_at == changed_at
    assert transition.reason == "Project paused."

    loaded = registry.load(
        stored.project_direction_id
    )

    assert loaded is not None
    assert loaded.project_status == "archived"
    assert registry.list_project_status_transitions(
        stored.project_id
    ) == [transition]


def test_project_status_transition_is_idempotent(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    result = registry.transition_project_status(
        stored.project_id,
        new_status="active",
        changed_at=CREATED_AT,
        reason="No change.",
    )

    assert result is None
    assert registry.list_project_status_transitions(
        stored.project_id
    ) == []


def test_archived_project_can_be_reactivated(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    registry.transition_project_status(
        stored.project_id,
        new_status="archived",
        changed_at=CREATED_AT,
    )
    reactivated = registry.transition_project_status(
        stored.project_id,
        new_status="active",
        changed_at=datetime(
            2026,
            7,
            14,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert reactivated is not None
    assert reactivated.previous_status == "archived"
    assert reactivated.new_status == "active"

    replacement = registry.create(
        create_stored_roadmap_snapshot(
            project_id=stored.project_id,
            response_direction_id="direction-two",
            title="Lifecycle project",
            snapshot=_snapshot(
                purpose="Resume the project."
            ),
            created_at=datetime(
                2026,
                7,
                14,
                17,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert replacement.project_status == "active"


@pytest.mark.parametrize(
    "initial_status",
    ["active", "archived"],
)
def test_project_can_be_soft_deleted(
    tmp_path: Path,
    initial_status: str,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    if initial_status == "archived":
        registry.transition_project_status(
            stored.project_id,
            new_status="archived",
            changed_at=CREATED_AT,
        )

    transition = registry.transition_project_status(
        stored.project_id,
        new_status="deleted",
        changed_at=datetime(
            2026,
            7,
            14,
            18,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert transition is not None
    assert transition.previous_status == initial_status
    assert transition.new_status == "deleted"


@pytest.mark.parametrize(
    "target_status",
    ["active", "archived"],
)
def test_deleted_project_cannot_transition(
    tmp_path: Path,
    target_status: str,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )
    stored = registry.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    registry.transition_project_status(
        stored.project_id,
        new_status="deleted",
        changed_at=CREATED_AT,
    )

    with pytest.raises(
        ProjectStatusTransitionError,
        match=(
            f"deleted -> {target_status}"
        ),
    ):
        registry.transition_project_status(
            stored.project_id,
            new_status=target_status,
            changed_at=CREATED_AT,
        )


def test_project_status_transition_is_workspace_scoped(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    first = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-one",
    )
    second = SQLiteRoadmapSnapshotRegistry(
        database_path,
        workspace_id="workspace-two",
    )
    stored = first.create(
        create_stored_roadmap_snapshot(
            project_id="proj_status",
            response_direction_id="direction-one",
            title="Lifecycle project",
            snapshot=_snapshot(),
            created_at=CREATED_AT,
        )
    )

    with pytest.raises(
        ProjectNotFoundError,
        match="not found",
    ):
        second.transition_project_status(
            stored.project_id,
            new_status="archived",
            changed_at=CREATED_AT,
        )

    assert first.load(
        stored.project_direction_id
    ).project_status == "active"


def test_project_status_transition_requires_existing_project(
    tmp_path: Path,
):
    registry = SQLiteRoadmapSnapshotRegistry(
        tmp_path / "solvyn.db"
    )

    with pytest.raises(
        ProjectNotFoundError,
        match="not found",
    ):
        registry.transition_project_status(
            "proj_missing",
            new_status="archived",
            changed_at=CREATED_AT,
        )
