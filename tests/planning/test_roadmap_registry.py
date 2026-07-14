from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from planning.roadmap_registry import (
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


def test_factory_creates_opaque_project_direction_id():
    record = create_stored_roadmap_snapshot(
        response_direction_id="direction-1",
        title="Evidence Attribution Engine",
        snapshot=_snapshot(),
        created_at=CREATED_AT,
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
        match="constraint conflict",
    ):
        registry.create(
            _record(
                project_direction_id="replacement",
                supersedes_id="missing",
            )
        )
