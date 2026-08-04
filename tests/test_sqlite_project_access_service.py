from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
    ProjectAccessStoreError,
)
from execution_evidence.sqlite_project_access_service import (
    SQLiteProjectAccessService,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)


NOW = datetime(
    2026,
    8,
    4,
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
MEMBERSHIP_ONE = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)
MEMBERSHIP_TWO = (
    "wsm_123e4567-e89b-42d3-a456-426614174004"
)

WORKSPACE_ONE = "workspace-one"
WORKSPACE_TWO = "workspace-two"
PROJECT_ID = "proj-shared"


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _principal() -> AuthenticatedRequestPrincipal:
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://issuer.example",
        subject="subject-123",
    )


def _insert_principal(
    connection,
    *,
    status: str = "active",
) -> None:
    connection.execute(
        """
        INSERT INTO principals (
            principal_id,
            principal_kind,
            status,
            created_at,
            updated_at
        )
        VALUES (?, 'human', ?, ?, ?)
        """,
        (
            PRINCIPAL_ID,
            status,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_workspace(
    connection,
    workspace_id: str,
) -> None:
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


def _insert_membership(
    connection,
    *,
    membership_id: str,
    workspace_id: str,
    status: str = "active",
) -> None:
    connection.execute(
        """
        INSERT INTO workspace_memberships (
            membership_id,
            workspace_id,
            principal_id,
            status,
            revision,
            created_by_principal_id,
            created_at,
            updated_at,
            status_changed_at
        )
        VALUES (?, ?, ?, ?, 0, NULL, ?, ?, ?)
        """,
        (
            membership_id,
            workspace_id,
            PRINCIPAL_ID,
            status,
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_project(
    connection,
    *,
    workspace_id: str,
    project_id: str = PROJECT_ID,
) -> None:
    connection.execute(
        """
        INSERT INTO projects (
            project_id,
            workspace_id,
            title,
            status,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'Test project', 'active', ?, ?)
        """,
        (
            project_id,
            workspace_id,
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _setup(
    path: Path,
    *,
    principal_status: str = "active",
    membership_status: str = "active",
) -> None:
    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        _insert_principal(
            connection,
            status=principal_status,
        )
        _insert_workspace(
            connection,
            WORKSPACE_ONE,
        )
        _insert_membership(
            connection,
            membership_id=MEMBERSHIP_ONE,
            workspace_id=WORKSPACE_ONE,
            status="active",
        )
        _insert_project(
            connection,
            workspace_id=WORKSPACE_ONE,
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    if membership_status != "active":
        SQLiteWorkspaceMembershipStore(
            path,
            workspace_id=WORKSPACE_ONE,
        ).transition_status(
            MEMBERSHIP_ONE,
            new_status=membership_status,
            changed_at=(
                NOW + timedelta(seconds=1)
            ),
            expected_revision=0,
            reason="authorization test setup",
        )


def test_authorizes_active_workspace_membership(
    database_path: Path,
):
    _setup(database_path)

    context = SQLiteProjectAccessService(
        database_path
    ).authorize(
        principal=_principal(),
        workspace_id=WORKSPACE_ONE,
        project_id=PROJECT_ID,
    )

    assert context.principal_id == PRINCIPAL_ID
    assert context.membership_id == MEMBERSHIP_ONE
    assert context.membership_role is None
    assert context.workspace_id == WORKSPACE_ONE
    assert context.project_id == PROJECT_ID


@pytest.mark.parametrize(
    "membership_status",
    [
        "suspended",
        "removed",
    ],
)
def test_inactive_membership_collapses_to_not_found(
    database_path: Path,
    membership_status: str,
):
    _setup(
        database_path,
        membership_status=membership_status,
    )

    with pytest.raises(
        ProjectAccessNotFoundError,
        match="Project does not exist",
    ):
        SQLiteProjectAccessService(
            database_path
        ).authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ONE,
            project_id=PROJECT_ID,
        )


@pytest.mark.parametrize(
    "principal_status",
    [
        "suspended",
        "deactivated",
    ],
)
def test_inactive_principal_fails_closed(
    database_path: Path,
    principal_status: str,
):
    _setup(
        database_path,
        principal_status=principal_status,
    )

    with pytest.raises(
        ProjectAccessNotFoundError,
        match="Project does not exist",
    ):
        SQLiteProjectAccessService(
            database_path
        ).authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ONE,
            project_id=PROJECT_ID,
        )


def test_membership_in_other_workspace_does_not_grant_access(
    database_path: Path,
):
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        _insert_principal(connection)
        _insert_workspace(
            connection,
            WORKSPACE_ONE,
        )
        _insert_workspace(
            connection,
            WORKSPACE_TWO,
        )

        _insert_membership(
            connection,
            membership_id=MEMBERSHIP_TWO,
            workspace_id=WORKSPACE_TWO,
        )

        _insert_project(
            connection,
            workspace_id=WORKSPACE_ONE,
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    with pytest.raises(
        ProjectAccessNotFoundError
    ):
        SQLiteProjectAccessService(
            database_path
        ).authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ONE,
            project_id=PROJECT_ID,
        )


def test_same_project_id_in_two_workspaces_is_not_ambiguous(
    database_path: Path,
):
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        _insert_principal(connection)

        _insert_workspace(
            connection,
            WORKSPACE_ONE,
        )
        _insert_workspace(
            connection,
            WORKSPACE_TWO,
        )

        _insert_membership(
            connection,
            membership_id=MEMBERSHIP_ONE,
            workspace_id=WORKSPACE_ONE,
        )

        _insert_project(
            connection,
            workspace_id=WORKSPACE_ONE,
        )
        _insert_project(
            connection,
            workspace_id=WORKSPACE_TWO,
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    service = SQLiteProjectAccessService(
        database_path
    )

    context = service.authorize(
        principal=_principal(),
        workspace_id=WORKSPACE_ONE,
        project_id=PROJECT_ID,
    )

    assert context.workspace_id == WORKSPACE_ONE

    with pytest.raises(
        ProjectAccessNotFoundError
    ):
        service.authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_TWO,
            project_id=PROJECT_ID,
        )


def test_missing_project_and_missing_membership_are_indistinguishable(
    database_path: Path,
):
    _setup(database_path)

    service = SQLiteProjectAccessService(
        database_path
    )

    with pytest.raises(
        ProjectAccessNotFoundError
    ) as missing_project:
        service.authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ONE,
            project_id="proj-missing",
        )

    with pytest.raises(
        ProjectAccessNotFoundError
    ) as wrong_workspace:
        service.authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_TWO,
            project_id=PROJECT_ID,
        )

    assert str(missing_project.value) == (
        str(wrong_workspace.value)
    )


def test_requires_authenticated_principal_type(
    database_path: Path,
):
    with pytest.raises(
        TypeError,
        match="authenticated request principal",
    ):
        SQLiteProjectAccessService(
            database_path
        ).authorize(
            principal=PRINCIPAL_ID,
            workspace_id=WORKSPACE_ONE,
            project_id=PROJECT_ID,
        )


@pytest.mark.parametrize(
    ("workspace_id", "project_id"),
    [
        ("", PROJECT_ID),
        (" workspace-one ", PROJECT_ID),
        (WORKSPACE_ONE, ""),
        (WORKSPACE_ONE, " proj-shared "),
    ],
)
def test_rejects_noncanonical_scope_selector(
    database_path: Path,
    workspace_id: str,
    project_id: str,
):
    with pytest.raises(ValueError):
        SQLiteProjectAccessService(
            database_path
        ).authorize(
            principal=_principal(),
            workspace_id=workspace_id,
            project_id=project_id,
        )


def test_service_does_not_initialize_schema(
    tmp_path: Path,
):
    path = tmp_path / "missing.db"

    with pytest.raises(
        ProjectAccessStoreError
    ):
        SQLiteProjectAccessService(
            path
        ).authorize(
            principal=_principal(),
            workspace_id=WORKSPACE_ONE,
            project_id=PROJECT_ID,
        )
