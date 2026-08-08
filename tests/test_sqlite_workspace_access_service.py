from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal import (
    Principal,
    create_principal_id,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.sqlite_workspace_access_service import (
    SQLiteWorkspaceAccessService,
)
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace_access_service import (
    WorkspaceAccessNotFoundError,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    create_workspace_membership_id,
)


NOW = datetime(
    2026,
    8,
    7,
    12,
    0,
    tzinfo=timezone.utc,
)

WORKSPACE_A = "workspace-access-a"
WORKSPACE_B = "workspace-access-b"


def _principal(
    principal_id: str,
) -> Principal:
    return Principal(
        principal_id=principal_id,
        principal_kind="human",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _request_principal(
    principal_id: str,
) -> AuthenticatedRequestPrincipal:
    return AuthenticatedRequestPrincipal(
        principal_id=principal_id,
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-426614174001"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
        issuer="https://issuer.example",
        subject="subject-123",
    )


def _membership(
    *,
    principal_id: str,
    workspace_id: str,
) -> WorkspaceMembership:
    return WorkspaceMembership(
        membership_id=create_workspace_membership_id(),
        workspace_id=workspace_id,
        principal_id=principal_id,
        status="active",
        role=None,
        revision=0,
        created_by_principal_id=None,
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )


def _create_workspace(
    path: Path,
    workspace_id: str,
) -> None:
    connection = connect_execution_evidence_database(
        path
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
                workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _setup(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)

    _create_workspace(path, WORKSPACE_A)
    _create_workspace(path, WORKSPACE_B)

    principal_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        _principal(principal_id)
    )

    membership_store = (
        SQLiteWorkspaceMembershipStore(
            path,
            workspace_id=WORKSPACE_A,
        )
    )

    membership = membership_store.create(
        _membership(
            principal_id=principal_id,
            workspace_id=WORKSPACE_A,
        )
    )

    return (
        path,
        principal_id,
        membership_store,
        membership,
    )


def test_active_member_is_authorized(
    tmp_path: Path,
):
    path, principal_id, _, membership = (
        _setup(tmp_path)
    )

    context = SQLiteWorkspaceAccessService(
        path
    ).authorize(
        principal=_request_principal(
            principal_id
        ),
        workspace_id=WORKSPACE_A,
    )

    assert context.principal_id == principal_id
    assert context.membership_id == (
        membership.membership_id
    )
    assert context.workspace_id == WORKSPACE_A


def test_non_member_is_hidden_as_not_found(
    tmp_path: Path,
):
    path, _, _, _ = _setup(tmp_path)

    outsider_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        _principal(outsider_id)
    )

    with pytest.raises(
        WorkspaceAccessNotFoundError
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                outsider_id
            ),
            workspace_id=WORKSPACE_A,
        )


def test_cross_workspace_member_is_hidden_as_not_found(
    tmp_path: Path,
):
    path, principal_id, _, _ = _setup(tmp_path)

    with pytest.raises(
        WorkspaceAccessNotFoundError
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                principal_id
            ),
            workspace_id=WORKSPACE_B,
        )


@pytest.mark.parametrize(
    "new_status",
    [
        "suspended",
        "removed",
    ],
)
def test_inactive_membership_is_hidden_as_not_found(
    tmp_path: Path,
    new_status,
):
    (
        path,
        principal_id,
        membership_store,
        membership,
    ) = _setup(tmp_path)

    membership_store.transition_status(
        membership.membership_id,
        new_status=new_status,
        changed_at=NOW,
        expected_revision=membership.revision,
    )

    with pytest.raises(
        WorkspaceAccessNotFoundError
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                principal_id
            ),
            workspace_id=WORKSPACE_A,
        )


def test_inactive_principal_is_hidden_as_not_found(
    tmp_path: Path,
):
    path, principal_id, _, _ = _setup(tmp_path)

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            UPDATE principals
            SET
                status = 'suspended',
                updated_at = ?
            WHERE principal_id = ?
            """,
            (
                NOW.isoformat(),
                principal_id,
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        WorkspaceAccessNotFoundError
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                principal_id
            ),
            workspace_id=WORKSPACE_A,
        )


def test_missing_workspace_is_hidden_as_not_found(
    tmp_path: Path,
):
    path, principal_id, _, _ = _setup(tmp_path)

    with pytest.raises(
        WorkspaceAccessNotFoundError
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                principal_id
            ),
            workspace_id="workspace-missing",
        )


def test_invalid_workspace_scope_fails_loudly(
    tmp_path: Path,
):
    path, principal_id, _, _ = _setup(tmp_path)

    with pytest.raises(
        ValueError,
        match="surrounding whitespace",
    ):
        SQLiteWorkspaceAccessService(
            path
        ).authorize(
            principal=_request_principal(
                principal_id
            ),
            workspace_id=f" {WORKSPACE_A} ",
        )
