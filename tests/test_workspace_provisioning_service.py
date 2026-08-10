from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

import execution_evidence.workspace_provisioning as provisioning
from execution_evidence.principal import Principal
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
    WorkspaceProvisioningIdentityCollisionError,
    WorkspaceProvisioningPrincipalUnavailableError,
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


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"

    initialize_execution_evidence_database(
        path
    )

    return path


def _principal(
    path: Path,
    *,
    principal_id: str = PRINCIPAL_ID,
    status: str = "active",
):
    return SQLitePrincipalStore(path).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status=status,
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _count(
    path: Path,
    table: str,
) -> int:
    allowed = {
        "workspaces",
        "workspace_memberships",
        "workspace_membership_status_transitions",
        "workspace_membership_role_transitions",
    }

    if table not in allowed:
        raise ValueError("Unexpected table.")

    connection = connect_execution_evidence_database(
        path
    )

    try:
        return int(
            connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM {table}
                """
            ).fetchone()["count"]
        )
    finally:
        connection.close()


def test_provision_creates_atomic_first_owner_graph(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path)

    result = SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
        reason="  initial self-service owner  ",
    )

    assert result.workspace.workspace_kind == (
        "provisioned"
    )
    assert result.workspace.workspace_id.startswith(
        "wsp_"
    )

    workspace_uuid = UUID(
        result.workspace.workspace_id[
            len("wsp_"):
        ]
    )
    assert workspace_uuid.version == 4

    assert result.membership.workspace_id == (
        result.workspace.workspace_id
    )
    assert result.membership.principal_id == (
        PRINCIPAL_ID
    )
    assert result.membership.status == "active"
    assert result.membership.role == "owner"
    assert result.membership.revision == 1
    assert (
        result.membership.created_by_principal_id
        == PRINCIPAL_ID
    )
    assert result.membership.created_at == NOW
    assert result.membership.updated_at == NOW
    assert (
        result.membership.status_changed_at
        == NOW
    )

    assert (
        result.owner_transition.membership_id
        == result.membership.membership_id
    )
    assert (
        result.owner_transition.workspace_id
        == result.workspace.workspace_id
    )
    assert (
        result.owner_transition.principal_id
        == PRINCIPAL_ID
    )
    assert (
        result.owner_transition.previous_role
        is None
    )
    assert (
        result.owner_transition.new_role
        == "owner"
    )
    assert (
        result.owner_transition.previous_revision
        == 0
    )
    assert (
        result.owner_transition.resulting_revision
        == 1
    )
    assert (
        result.owner_transition
        .changed_by_principal_id
        is None
    )
    assert (
        result.owner_transition.reason
        == "initial self-service owner"
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        workspace = connection.execute(
            """
            SELECT
                workspace_kind,
                created_at,
                updated_at
            FROM workspaces
            WHERE workspace_id = ?
            """,
            (result.workspace.workspace_id,),
        ).fetchone()

        genesis = connection.execute(
            """
            SELECT
                previous_status,
                new_status,
                previous_revision,
                resulting_revision,
                changed_at,
                changed_by_principal_id
            FROM workspace_membership_status_transitions
            WHERE
                membership_id = ?
                AND resulting_revision = 0
            """,
            (result.membership.membership_id,),
        ).fetchone()

        role_transition = connection.execute(
            """
            SELECT
                previous_role,
                new_role,
                previous_revision,
                resulting_revision,
                changed_at,
                changed_by_principal_id,
                reason
            FROM workspace_membership_role_transitions
            WHERE role_transition_id = ?
            """,
            (
                result.owner_transition
                .transition_id,
            ),
        ).fetchone()
    finally:
        connection.close()

    assert workspace is not None
    assert workspace["workspace_kind"] == (
        "provisioned"
    )
    assert workspace["created_at"] == (
        NOW.isoformat()
    )
    assert workspace["updated_at"] == (
        NOW.isoformat()
    )

    assert genesis is not None
    assert genesis["previous_status"] is None
    assert genesis["new_status"] == "active"
    assert genesis["previous_revision"] is None
    assert int(
        genesis["resulting_revision"]
    ) == 0
    assert genesis["changed_at"] == NOW.isoformat()
    assert (
        genesis["changed_by_principal_id"]
        is None
    )

    assert role_transition is not None
    assert role_transition["previous_role"] is None
    assert role_transition["new_role"] == "owner"
    assert int(
        role_transition["previous_revision"]
    ) == 0
    assert int(
        role_transition["resulting_revision"]
    ) == 1
    assert (
        role_transition["changed_at"]
        == NOW.isoformat()
    )
    assert (
        role_transition[
            "changed_by_principal_id"
        ]
        is None
    )
    assert (
        role_transition["reason"]
        == "initial self-service owner"
    )


@pytest.mark.parametrize(
    "status",
    [
        "suspended",
        "deactivated",
    ],
)
def test_provision_revalidates_active_principal(
    tmp_path: Path,
    status: str,
):
    path = _database(tmp_path)
    _principal(
        path,
        status=status,
    )

    with pytest.raises(
        WorkspaceProvisioningPrincipalUnavailableError,
        match="does not exist or is not active",
    ):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_ID,
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 0
    )
    assert (
        _count(
            path,
            "workspace_membership_role_transitions",
        )
        == 0
    )


def test_provision_requires_existing_principal(
    tmp_path: Path,
):
    path = _database(tmp_path)

    with pytest.raises(
        WorkspaceProvisioningPrincipalUnavailableError,
    ):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_ID,
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0


def test_provision_requires_timezone_aware_timestamp(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path)

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_ID,
            created_at=datetime(
                2026,
                8,
                10,
                12,
                0,
            ),
        )

    assert _count(path, "workspaces") == 0


def test_provision_rolls_back_graph_when_owner_transition_validation_fails(
    tmp_path: Path,
    monkeypatch,
):
    path = _database(tmp_path)
    _principal(path)

    monkeypatch.setattr(
        provisioning,
        "create_workspace_membership_role_transition_id",
        lambda: "invalid-transition-id",
    )

    with pytest.raises(ValidationError):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_ID,
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 0
    )
    assert (
        _count(
            path,
            "workspace_membership_status_transitions",
        )
        == 0
    )
    assert (
        _count(
            path,
            "workspace_membership_role_transitions",
        )
        == 0
    )


def test_workspace_identity_collision_fails_without_partial_graph(
    tmp_path: Path,
    monkeypatch,
):
    path = _database(tmp_path)
    _principal(path)

    collided_id = (
        "wsp_123e4567-e89b-42d3-a456-426614174001"
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at,
                workspace_kind
            )
            VALUES (?, ?, ?, 'provisioned')
            """,
            (
                collided_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    monkeypatch.setattr(
        provisioning,
        "create_workspace_id",
        lambda: collided_id,
    )

    with pytest.raises(
        WorkspaceProvisioningIdentityCollisionError,
        match="workspace identity collided",
    ):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_ID,
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 0
    )
    assert (
        _count(
            path,
            "workspace_membership_status_transitions",
        )
        == 0
    )
    assert (
        _count(
            path,
            "workspace_membership_role_transitions",
        )
        == 0
    )


def test_two_non_idempotent_provisions_create_distinct_workspaces(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    first = service.provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
    )

    second = service.provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
    )

    assert (
        first.workspace.workspace_id
        != second.workspace.workspace_id
    )

    assert _count(path, "workspaces") == 2
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 2
    )

    # H1 intentionally has no request idempotency contract.
    # H2 will make retries resolve to one provisioning graph.
