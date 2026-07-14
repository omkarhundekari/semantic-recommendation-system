import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RepositorySyncState,
    RoadmapAttributionContext,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
    SQLiteRepositoryEvidenceStoreError,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
    StoredRoadmapSnapshot,
)
from planning.roadmap_snapshot import (
    RoadmapSnapshot,
    RoadmapStageSnapshot,
)
from execution_evidence.store import (
    RepositoryEvidenceRestoreError,
    StoredRepositoryEvidence,
)
SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)


def _record(
    *,
    with_attribution: bool = False,
) -> StoredRepositoryEvidence:
    evidence = ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id="abc123",
        title="Implement SQLite evidence storage",
        url=(
            f"{REFERENCE.canonical_url}/commit/"
            "abc123"
        ),
        occurred_at=SAVED_AT,
        metadata={
            "files": [
                "src/execution_evidence/sqlite_store.py"
            ],
        },
        first_seen_at=SAVED_AT,
        last_seen_at=SAVED_AT,
    )

    attributions = []

    if with_attribution:
        attributions.append(
            EvidenceAttribution(
                evidence_key=evidence.evidence_key,
                roadmap_node_id="persist-evidence",
                source="deterministic",
                confidence=0.84,
                rationale=(
                    "Commit title matches the persistence "
                    "roadmap stage."
                ),
                status="suggested",
                decided_at=None,
            )
        )

    return StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[evidence],
        attributions=attributions,
        sync_state=RepositorySyncState(
            repository_key=REFERENCE.repository_key,
            status="succeeded",
            latest_commit_sha="abc123",
            last_attempted_at=SAVED_AT,
            last_succeeded_at=SAVED_AT,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REFERENCE.repository_key,
        ),
        saved_at=SAVED_AT,
    )


def test_sqlite_store_persists_across_instances(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    saved = SQLiteRepositoryEvidenceStore(
        database_path
    ).save(
        _record(with_attribution=True)
    )

    loaded = SQLiteRepositoryEvidenceStore(
        database_path
    ).load(REFERENCE.repository_key)

    assert loaded == saved
    assert loaded is not saved
    assert loaded is not None
    assert loaded.attributions[0].decided_at is None


def test_sqlite_store_preserves_nested_json_payloads(
    tmp_path: Path,
):
    store = SQLiteRepositoryEvidenceStore(
        tmp_path / "solvyn.db"
    )

    saved = store.save(_record())
    loaded = store.load(
        REFERENCE.repository_key
    )

    assert loaded == saved
    assert loaded is not None
    assert loaded.evidence[0].metadata == {
        "files": [
            "src/execution_evidence/sqlite_store.py"
        ],
    }


def test_sqlite_store_rolls_back_failed_aggregate_write(
    tmp_path: Path,
    monkeypatch,
):
    store = SQLiteRepositoryEvidenceStore(
        tmp_path / "solvyn.db"
    )
    first = store.save(_record())

    def fail_attributions(*args, **kwargs):
        raise sqlite3.IntegrityError(
            "forced attribution failure"
        )

    monkeypatch.setattr(
        store,
        "_write_attributions",
        fail_attributions,
    )

    with pytest.raises(
        SQLiteRepositoryEvidenceStoreError,
        match="Could not save",
    ):
        store.save(
            first,
            expected_revision=first.revision,
        )

    loaded = SQLiteRepositoryEvidenceStore(
        store.path
    ).load(REFERENCE.repository_key)

    assert loaded == first


def test_sqlite_store_isolates_workspaces(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    first_store = SQLiteRepositoryEvidenceStore(
        database_path,
        workspace_id="workspace-one",
    )
    second_store = SQLiteRepositoryEvidenceStore(
        database_path,
        workspace_id="workspace-two",
    )

    first_store.save(_record())

    assert first_store.list_repository_keys() == [
        REFERENCE.repository_key
    ]
    assert second_store.list_repository_keys() == []
    assert (
        second_store.load(
            REFERENCE.repository_key
        )
        is None
    )


def test_sqlite_delete_cascades_aggregate_rows(
    tmp_path: Path,
):
    store = SQLiteRepositoryEvidenceStore(
        tmp_path / "solvyn.db"
    )
    store.save(
        _record(with_attribution=True)
    )

    assert (
        store.delete(
            REFERENCE.repository_key
        )
        is True
    )

    connection = (
        connect_execution_evidence_database(
            store.path
        )
    )

    try:
        assert connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM evidence_items
            """
        ).fetchone()["count"] == 0

        assert connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM evidence_attributions
            """
        ).fetchone()["count"] == 0

        assert connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM repository_sync_states
            """
        ).fetchone()["count"] == 0

        assert connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM repository_sync_snapshots
            """
        ).fetchone()["count"] == 0
    finally:
        connection.close()


def test_sqlite_restore_rolls_back_mid_batch_failure(
    tmp_path: Path,
    monkeypatch,
):
    store = SQLiteRepositoryEvidenceStore(
        tmp_path / "solvyn.db"
    )

    first_record = _record()
    second_reference = (
        parse_github_repository_url(
            "https://github.com/example/second"
        )
    )
    second_record = first_record.model_copy(
        update={
            "repository": second_reference,
            "evidence": [],
            "attributions": [],
            "sync_state": RepositorySyncState(
                repository_key=(
                    second_reference.repository_key
                ),
            ),
            "sync_snapshot": (
                GitHubRepositorySyncSnapshot(
                    repository_key=(
                        second_reference.repository_key
                    ),
                )
            ),
            "revision": 6,
        },
        deep=True,
    )

    original_writer = (
        store._restore_record_on_connection
    )
    call_count = 0

    def fail_second_record(
        connection,
        record,
    ):
        nonlocal call_count
        call_count += 1

        if call_count == 2:
            raise sqlite3.IntegrityError(
                "forced restore failure"
            )

        original_writer(
            connection,
            record,
        )

    monkeypatch.setattr(
        store,
        "_restore_record_on_connection",
        fail_second_record,
    )

    with pytest.raises(
        RepositoryEvidenceRestoreError,
        match="Could not restore",
    ):
        store.restore(
            [
                first_record,
                second_record,
            ]
        )

    assert store.list_repository_keys() == []


def _trusted_context() -> RoadmapAttributionContext:
    return RoadmapAttributionContext(
        roadmap_hash="a" * 64,
        roadmap_stage_hash="b" * 64,
        roadmap_node_id="persist-evidence",
        snapshot_version=1,
        canonicalization_version=1,
    )


def _register_project_direction(
    database_path: Path,
    *,
    project_direction_id: str,
) -> None:
    registry = SQLiteRoadmapSnapshotRegistry(
        database_path
    )
    registry.create(
        StoredRoadmapSnapshot(
            project_direction_id=(
                project_direction_id
            ),
            response_direction_id="direction-one",
            title="Trusted direction",
            snapshot=RoadmapSnapshot(
                roadmap_hash="a" * 64,
                snapshot_version=1,
                canonicalization_version=1,
                stages=[
                    RoadmapStageSnapshot(
                        stage_id="persist-evidence",
                        position=0,
                        content_hash="b" * 64,
                        content={
                            "id": "persist-evidence",
                            "title": (
                                "Persist execution evidence"
                            ),
                        },
                    )
                ],
            ),
            created_at=SAVED_AT,
        )
    )


def test_sqlite_store_persists_project_scoped_attribution(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _register_project_direction(
        database_path,
        project_direction_id="project-one",
    )

    record = _record()
    evidence = record.evidence[0]
    attribution = EvidenceAttribution(
        attribution_id="attribution-one",
        project_direction_id="project-one",
        evidence_key=evidence.evidence_key,
        roadmap_node_id="persist-evidence",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=SAVED_AT,
        roadmap_context=_trusted_context(),
    )

    saved = SQLiteRepositoryEvidenceStore(
        database_path
    ).save(
        record.model_copy(
            update={
                "attributions": [attribution],
            },
            deep=True,
        )
    )

    loaded = SQLiteRepositoryEvidenceStore(
        database_path
    ).load(REFERENCE.repository_key)

    assert loaded == saved
    assert loaded is not None
    assert (
        loaded.attributions[0].attribution_id
        == "attribution-one"
    )
    assert (
        loaded.attributions[0]
        .project_direction_id
        == "project-one"
    )


def test_sqlite_store_rejects_unknown_project_direction(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    store = SQLiteRepositoryEvidenceStore(
        database_path
    )
    record = _record()
    evidence = record.evidence[0]

    attribution = EvidenceAttribution(
        attribution_id="attribution-one",
        project_direction_id="missing-project",
        evidence_key=evidence.evidence_key,
        roadmap_node_id="persist-evidence",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=SAVED_AT,
        roadmap_context=_trusted_context(),
    )

    with pytest.raises(
        SQLiteRepositoryEvidenceStoreError,
        match="unknown roadmap snapshot",
    ):
        store.save(
            record.model_copy(
                update={
                    "attributions": [attribution],
                },
                deep=True,
            )
        )
