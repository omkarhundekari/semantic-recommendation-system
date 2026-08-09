from pathlib import Path

import pytest

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)

from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
)


PROVISIONED_WORKSPACE_ID = (
    "wsp_123e4567-e89b-42d3-a456-426614174000"
)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _workspace_row(
    path: Path,
    workspace_id: str,
):
    connection = connect_execution_evidence_database(
        path
    )

    try:
        return connection.execute(
            """
            SELECT
                workspace_id,
                workspace_kind,
                created_at,
                updated_at
            FROM workspaces
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()
    finally:
        connection.close()


def test_implicit_ensure_creates_only_internal_workspace(
    tmp_path: Path,
):
    path = _database(tmp_path)
    workspace_id = "internal-workspace"

    store = SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
    )

    row = _workspace_row(
        path,
        workspace_id,
    )

    assert store.workspace_id == workspace_id
    assert row is not None
    assert row["workspace_kind"] == "internal"


def test_implicit_ensure_does_not_mutate_existing_metadata(
    tmp_path: Path,
):
    path = _database(tmp_path)
    workspace_id = "existing-internal-workspace"

    SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
    )

    created_at = "2000-01-01T00:00:00+00:00"
    updated_at = "2001-01-01T00:00:00+00:00"

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            UPDATE workspaces
            SET
                created_at = ?,
                updated_at = ?
            WHERE workspace_id = ?
            """,
            (
                created_at,
                updated_at,
                workspace_id,
            ),
        )
    finally:
        connection.close()

    SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
    )

    row = _workspace_row(
        path,
        workspace_id,
    )

    assert row is not None
    assert row["workspace_kind"] == "internal"
    assert row["created_at"] == created_at
    assert row["updated_at"] == updated_at


def test_implicit_ensure_rejects_provisioned_namespace(
    tmp_path: Path,
):
    path = _database(tmp_path)

    with pytest.raises(
        ValueError,
        match="reserved provisioned workspace ID",
    ):
        SQLiteRepositoryEvidenceStore(
            path,
            workspace_id=PROVISIONED_WORKSPACE_ID,
            initialize_schema=False,
        )

    assert (
        _workspace_row(
            path,
            PROVISIONED_WORKSPACE_ID,
        )
        is None
    )


def test_non_ensuring_store_can_bind_provisioned_workspace(
    tmp_path: Path,
):
    path = _database(tmp_path)

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                workspace_kind,
                created_at,
                updated_at
            )
            VALUES (?, 'provisioned', ?, ?)
            """,
            (
                PROVISIONED_WORKSPACE_ID,
                "2026-08-09T12:00:00+00:00",
                "2026-08-09T12:00:00+00:00",
            ),
        )
    finally:
        connection.close()

    before = _workspace_row(
        path,
        PROVISIONED_WORKSPACE_ID,
    )

    store = SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=PROVISIONED_WORKSPACE_ID,
        initialize_schema=False,
        ensure_workspace=False,
    )

    after = _workspace_row(
        path,
        PROVISIONED_WORKSPACE_ID,
    )

    assert store.workspace_id == PROVISIONED_WORKSPACE_ID
    assert before is not None
    assert after is not None
    assert after["workspace_kind"] == "provisioned"
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] == before["updated_at"]


def test_skipping_ensure_does_not_create_missing_provisioned_workspace(
    tmp_path: Path,
):
    path = _database(tmp_path)

    store = SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=PROVISIONED_WORKSPACE_ID,
        initialize_schema=False,
        ensure_workspace=False,
    )

    assert store.workspace_id == PROVISIONED_WORKSPACE_ID
    assert (
        _workspace_row(
            path,
            PROVISIONED_WORKSPACE_ID,
        )
        is None
    )


def test_repository_store_ensures_workspace_without_schema_initialization(
    tmp_path: Path,
):
    path = _database(tmp_path)
    workspace_id = "repository-preinitialized-workspace"

    store = SQLiteRepositoryEvidenceStore(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
        ensure_workspace=True,
    )

    row = _workspace_row(
        path,
        workspace_id,
    )

    assert store.workspace_id == workspace_id
    assert row is not None
    assert row["workspace_kind"] == "internal"


def test_roadmap_registry_ensures_workspace_without_schema_initialization(
    tmp_path: Path,
):
    path = _database(tmp_path)
    workspace_id = "roadmap-preinitialized-workspace"

    registry = SQLiteRoadmapSnapshotRegistry(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
        ensure_workspace=True,
    )

    row = _workspace_row(
        path,
        workspace_id,
    )

    assert registry.workspace_id == workspace_id
    assert row is not None
    assert row["workspace_kind"] == "internal"
