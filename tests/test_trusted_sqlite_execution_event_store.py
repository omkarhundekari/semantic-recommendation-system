from pathlib import Path

import pytest

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174001"
)


def _authorized_context(
    *,
    workspace_id: str = "workspace-authorized",
    project_id: str = "project-authorized",
) -> AuthorizedProjectContext:
    return AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=workspace_id,
        project_id=project_id,
    )


def test_trusted_storage_service_builds_execution_event_store(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="workspace_test",
    )

    store = service.build_execution_event_store()

    assert isinstance(
        store,
        SQLiteExecutionEventStore,
    )
    assert store._path == database_path
    assert store._workspace_id == "workspace_test"


def test_trusted_storage_service_builds_workspace_bound_execution_event_store(
    tmp_path,
):
    from execution_evidence.storage_service import (
        TrustedSQLiteStorageService,
    )
    from execution_evidence.trusted_store import (
        initialize_fresh_trusted_store,
    )

    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path
    )

    store = (
        service
        .build_execution_event_store_for_workspace(
            "workspace-b"
        )
    )

    assert store.workspace_id == "workspace-b"
def test_trusted_storage_service_builds_store_from_authorized_project_context(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="workspace-default",
    )

    context = _authorized_context(
        workspace_id="workspace-authorized",
        project_id="project-authorized",
    )

    store = (
        service
        .build_execution_event_store_for_authorized_project(
            context
        )
    )

    assert isinstance(
        store,
        SQLiteExecutionEventStore,
    )
    assert store.path == database_path
    assert (
        store.workspace_id
        == context.workspace_id
    )
    assert (
        store.workspace_id
        != service.workspace_id
    )


@pytest.mark.parametrize(
    "untrusted_scope",
    [
        "workspace-authorized",
        {
            "workspace_id": "workspace-authorized",
            "project_id": "project-authorized",
        },
    ],
)
def test_authorized_project_store_factory_rejects_loose_scope(
    tmp_path: Path,
    untrusted_scope,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="workspace-default",
    )

    with pytest.raises(
        TypeError,
        match="authorized project context",
    ):
        (
            service
            .build_execution_event_store_for_authorized_project(
                untrusted_scope
            )
        )
