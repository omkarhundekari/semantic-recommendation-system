from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal import (
    Principal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
)
from execution_evidence.project_read_service import (
    ProjectReadNotFoundError,
    ProjectReadStoreError,
    SQLiteProjectReadService,
)
from execution_evidence.sqlite_project_access_service import (
    SQLiteProjectAccessService,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
)
from execution_evidence.workspace_owner_bootstrap import (
    SQLiteWorkspaceOwnerBootstrapService,
)
from product_api import (
    app,
    get_authorized_project_context,
    get_project_read_service,
)


NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174001"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174002"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)
OWNER_PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174010"
)
OWNER_MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174011"
)

WORKSPACE_ID = "workspace-project-read"
PROJECT_ID = "proj-project-read"


def _database(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )
    return path


def _principal() -> AuthenticatedRequestPrincipal:
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://issuer.example",
        subject="subject-project-read",
    )


def _setup(
    path: Path,
    *,
    status: str = "active",
    role: str | None = "viewer",
) -> None:
    principal_store = SQLitePrincipalStore(
        path
    )

    principal_store.create(
        Principal(
            principal_id=OWNER_PRINCIPAL_ID,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    principal_store.create(
        Principal(
            principal_id=PRINCIPAL_ID,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                WORKSPACE_ID,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    membership_store = (
        SQLiteWorkspaceMembershipStore(
            path,
            workspace_id=WORKSPACE_ID,
        )
    )

    owner = membership_store.create(
        WorkspaceMembership(
            membership_id=OWNER_MEMBERSHIP_ID,
            workspace_id=WORKSPACE_ID,
            principal_id=OWNER_PRINCIPAL_ID,
            status="active",
            role=None,
            revision=0,
            created_by_principal_id=None,
            created_at=NOW,
            updated_at=NOW,
            status_changed_at=NOW,
        )
    )

    target = membership_store.create(
        WorkspaceMembership(
            membership_id=MEMBERSHIP_ID,
            workspace_id=WORKSPACE_ID,
            principal_id=PRINCIPAL_ID,
            status="active",
            role=None,
            revision=0,
            created_by_principal_id=None,
            created_at=NOW,
            updated_at=NOW,
            status_changed_at=NOW,
        )
    )

    SQLiteWorkspaceOwnerBootstrapService(
        path
    ).bootstrap_first_owner(
        workspace_id=WORKSPACE_ID,
        membership_id=owner.membership_id,
        changed_at=(
            NOW + timedelta(seconds=1)
        ),
    )

    if role is not None:
        membership_store.transition_role(
            target.membership_id,
            new_role=role,
            changed_at=(
                NOW + timedelta(seconds=2)
            ),
            expected_revision=0,
            changed_by_principal_id=(
                OWNER_PRINCIPAL_ID
            ),
            reason=(
                "Project read test fixture role"
            ),
        )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                revision,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                'Project read test',
                ?,
                3,
                ?,
                ?
            )
            """,
            (
                PROJECT_ID,
                WORKSPACE_ID,
                status,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _context() -> AuthorizedProjectContext:
    return AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )


@pytest.mark.parametrize(
    "status",
    [
        "active",
        "archived",
    ],
)
def test_project_read_loads_active_and_archived(
    tmp_path: Path,
    status: str,
):
    path = _database(tmp_path)
    _setup(
        path,
        status=status,
    )

    record = SQLiteProjectReadService(
        path
    ).load(
        _context()
    )

    assert record.project_id == PROJECT_ID
    assert record.title == "Project read test"
    assert record.status == status
    assert record.revision == 3
    assert record.created_at == NOW
    assert record.updated_at == NOW


def test_project_read_uses_authorized_context_scope(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    wrong_context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id="wrong-workspace",
        project_id=PROJECT_ID,
    )

    with pytest.raises(
        ProjectReadNotFoundError
    ):
        SQLiteProjectReadService(
            path
        ).load(
            wrong_context
        )


def test_project_read_requires_authorized_context(
    tmp_path: Path,
):
    path = _database(tmp_path)

    with pytest.raises(
        TypeError,
        match="Authorized project context is required",
    ):
        SQLiteProjectReadService(
            path
        ).load(
            object()
        )


def test_project_read_rejects_invalid_stored_timestamp_as_store_failure(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                revision,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                'Invalid timestamp project',
                'active',
                0,
                ?,
                ?
            )
            """,
            (
                "proj-invalid-read-time",
                WORKSPACE_ID,
                "2026-08-10T12:00:00",
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id=WORKSPACE_ID,
        project_id="proj-invalid-read-time",
    )

    with pytest.raises(
        ProjectReadStoreError,
        match="Stored project metadata is invalid",
    ):
        SQLiteProjectReadService(
            path
        ).load(
            context
        )


def test_api_invalid_stored_project_metadata_returns_503(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    invalid_project_id = (
        "proj-invalid-api-read-time"
    )

    try:
        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                revision,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                'Invalid API timestamp project',
                'active',
                0,
                ?,
                ?
            )
            """,
            (
                invalid_project_id,
                WORKSPACE_ID,
                "2026-08-10T12:00:00",
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id=WORKSPACE_ID,
        project_id=invalid_project_id,
    )

    app.dependency_overrides[
        get_authorized_project_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_read_service
    ] = lambda: SQLiteProjectReadService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{WORKSPACE_ID}/projects/"
                    f"{invalid_project_id}"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Project read storage is "
            "temporarily unavailable."
        )
    }


def test_deleted_project_never_authorizes(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(
        path,
        status="deleted",
    )

    with pytest.raises(
        ProjectAccessNotFoundError,
        match="Project does not exist",
    ):
        SQLiteProjectAccessService(
            path
        ).authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ID,
            project_id=PROJECT_ID,
        )


def test_api_returns_project_detail(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    app.dependency_overrides[
        get_authorized_project_context
    ] = _context

    app.dependency_overrides[
        get_project_read_service
    ] = lambda: SQLiteProjectReadService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{WORKSPACE_ID}/projects/"
                    f"{PROJECT_ID}"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["project_id"] == PROJECT_ID
    assert body["title"] == "Project read test"
    assert body["status"] == "active"
    assert body["revision"] == 3


def test_api_archived_project_is_readable(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(
        path,
        status="archived",
    )

    app.dependency_overrides[
        get_authorized_project_context
    ] = _context

    app.dependency_overrides[
        get_project_read_service
    ] = lambda: SQLiteProjectReadService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{WORKSPACE_ID}/projects/"
                    f"{PROJECT_ID}"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_api_role_none_is_forbidden(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role=None,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )

    app.dependency_overrides[
        get_authorized_project_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_read_service
    ] = lambda: SQLiteProjectReadService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{WORKSPACE_ID}/projects/"
                    f"{PROJECT_ID}"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "project.read" in response.json()[
        "detail"
    ]


def test_api_uses_context_project_not_raw_path(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _setup(path)

    app.dependency_overrides[
        get_authorized_project_context
    ] = _context

    app.dependency_overrides[
        get_project_read_service
    ] = lambda: SQLiteProjectReadService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{WORKSPACE_ID}/projects/"
                    "different-path-project"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert (
        response.json()["project_id"]
        == PROJECT_ID
    )
