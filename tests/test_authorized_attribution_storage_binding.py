from pathlib import Path

import pytest

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_service import (
    ExecutionEvidenceStorageRuntime,
    TrustedSQLiteStorageService,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)
from product_api import (
    get_authorized_execution_evidence_attribution_service,
    get_authorized_roadmap_registry,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)
WORKSPACE_ID = "workspace-authorized"
PROJECT_ID = "project-authorized"


def _context() -> AuthorizedProjectContext:
    return AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="admin",
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )


def _trusted_service(
    tmp_path: Path,
) -> TrustedSQLiteStorageService:
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-08-07T12:00:00+00:00",
    )

    return TrustedSQLiteStorageService(
        database_path
    )


def _workspace_updated_at(
    database_path: Path,
    workspace_id: str,
):
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT updated_at
            FROM workspaces
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        return (
            None
            if row is None
            else str(row["updated_at"])
        )
    finally:
        connection.close()


def _set_workspace_updated_at(
    database_path: Path,
    workspace_id: str,
    updated_at: str,
) -> None:
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            UPDATE workspaces
            SET updated_at = ?
            WHERE workspace_id = ?
            """,
            (
                updated_at,
                workspace_id,
            ),
        )
    finally:
        connection.close()


def test_default_store_construction_still_ensures_workspace(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    store = SQLiteRepositoryEvidenceStore(
        service.path,
        workspace_id=WORKSPACE_ID,
        initialize_schema=False,
    )

    assert store.workspace_id == WORKSPACE_ID
    assert (
        _workspace_updated_at(
            service.path,
            WORKSPACE_ID,
        )
        is not None
    )


def test_store_can_skip_workspace_provisioning(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    store = SQLiteRepositoryEvidenceStore(
        service.path,
        workspace_id=WORKSPACE_ID,
        initialize_schema=False,
        ensure_workspace=False,
    )

    assert store.workspace_id == WORKSPACE_ID
    assert (
        _workspace_updated_at(
            service.path,
            WORKSPACE_ID,
        )
        is None
    )


def test_authorized_store_uses_context_workspace_without_write(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    SQLiteRepositoryEvidenceStore(
        service.path,
        workspace_id=WORKSPACE_ID,
        initialize_schema=False,
    )

    sentinel = "2001-01-01T00:00:00+00:00"

    _set_workspace_updated_at(
        service.path,
        WORKSPACE_ID,
        sentinel,
    )

    store = (
        service
        .build_repository_evidence_store_for_authorized_project(
            _context()
        )
    )

    assert store.workspace_id == WORKSPACE_ID
    assert (
        _workspace_updated_at(
            service.path,
            WORKSPACE_ID,
        )
        == sentinel
    )


def test_authorized_store_requires_authorized_context(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    with pytest.raises(
        TypeError,
        match="authorized project context",
    ):
        service.build_repository_evidence_store_for_authorized_project(
            object()
        )


def test_authorized_attribution_service_and_registry_share_workspace(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    SQLiteRepositoryEvidenceStore(
        service.path,
        workspace_id=WORKSPACE_ID,
        initialize_schema=False,
    )

    sentinel = "2001-01-01T00:00:00+00:00"

    _set_workspace_updated_at(
        service.path,
        WORKSPACE_ID,
        sentinel,
    )

    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=(
            service.build_repository_evidence_store()
        ),
        trusted_sqlite_service=service,
        roadmap_registry=(
            service.build_roadmap_snapshot_registry()
        ),
        roadmap_registry_status="ready",
        remediation=None,
    )

    context = _context()

    attribution_service = (
        get_authorized_execution_evidence_attribution_service(
            context=context,
            runtime=runtime,
        )
    )

    roadmap_registry = (
        get_authorized_roadmap_registry(
            context=context,
            runtime=runtime,
        )
    )

    attribution_store = (
        attribution_service._store
    )

    assert isinstance(
        attribution_store,
        SQLiteRepositoryEvidenceStore,
    )

    assert (
        attribution_store.workspace_id
        == context.workspace_id
    )
    assert (
        roadmap_registry.workspace_id
        == context.workspace_id
    )
    assert (
        attribution_store.workspace_id
        == roadmap_registry.workspace_id
    )

    assert (
        _workspace_updated_at(
            service.path,
            WORKSPACE_ID,
        )
        == sentinel
    )


def test_authorized_attribution_service_requires_trusted_sqlite(
    tmp_path: Path,
):
    service = _trusted_service(tmp_path)

    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=(
            service.build_repository_evidence_store()
        ),
        trusted_sqlite_service=None,
        roadmap_registry=(
            service.build_roadmap_snapshot_registry()
        ),
        roadmap_registry_status="ready",
        remediation=None,
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as raised:
        get_authorized_execution_evidence_attribution_service(
            context=_context(),
            runtime=runtime,
        )

    assert raised.value.status_code == 503
