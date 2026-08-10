from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest

import execution_evidence.workspace_discovery as workspace_discovery

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal import Principal
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.workspace_discovery import (
    SQLiteWorkspaceDiscoveryService,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    create_workspace_membership_id,
)
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace import (
    ProvisionedWorkspace,
    create_workspace_id,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
)


NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_A = (
    "prn_123e4567-e89b-42d3-a456-426614174100"
)

PRINCIPAL_B = (
    "prn_123e4567-e89b-42d3-a456-426614174101"
)


def _database(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path / "workspace-discovery.db"
    )

    initialize_execution_evidence_database(
        path
    )

    return path


def _principal(
    path: Path,
    principal_id: str,
    *,
    status: str = "active",
) -> None:
    SQLitePrincipalStore(path).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status=status,
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _authenticated(
    principal_id: str,
) -> AuthenticatedRequestPrincipal:
    suffix = (
        "110"
        if principal_id == PRINCIPAL_A
        else "120"
    )

    return AuthenticatedRequestPrincipal(
        principal_id=principal_id,
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-"
            f"426614174{suffix}"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-"
            f"426614174{int(suffix) + 1}"
        ),
        issuer="https://issuer.example",
        subject=f"subject-{principal_id}",
    )



def _authenticated_principal(
    principal_id: str,
) -> AuthenticatedRequestPrincipal:
    return AuthenticatedRequestPrincipal(
        principal_id=principal_id,
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-426614174090"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174091"
        ),
        issuer="https://issuer.example",
        subject=(
            "workspace-discovery-service-test"
        ),
    )

def test_discovery_returns_principal_owned_workspace(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=NOW,
            reason="workspace discovery test",
        )
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert len(discovered) == 1

    workspace = discovered[0]

    assert workspace.workspace_id == (
        provisioned.workspace.workspace_id
    )
    assert workspace.workspace_kind == (
        "provisioned"
    )
    assert workspace.membership_id == (
        provisioned.membership.membership_id
    )
    assert workspace.membership_role == "owner"
    assert workspace.membership_revision == 1


def test_discovery_is_strictly_principal_scoped(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    workspace_a = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=NOW,
        )
    )

    workspace_b = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_B,
            created_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert [
        item.workspace_id
        for item in discovered
    ] == [
        workspace_a.workspace.workspace_id
    ]

    assert (
        workspace_b.workspace.workspace_id
        not in {
            item.workspace_id
            for item in discovered
        }
    )


def test_discovery_excludes_suspended_membership(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    provisioned = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=NOW,
        )
    )

    membership_store = (
        SQLiteWorkspaceMembershipStore(
            path,
            workspace_id=(
                provisioned.workspace.workspace_id
            ),
        )
    )

    second_membership = WorkspaceMembership(
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id=(
            provisioned.workspace.workspace_id
        ),
        principal_id=PRINCIPAL_B,
        status="active",
        role=None,
        revision=0,
        created_by_principal_id=(
            PRINCIPAL_A
        ),
        created_at=(
            NOW + timedelta(seconds=1)
        ),
        updated_at=(
            NOW + timedelta(seconds=1)
        ),
        status_changed_at=(
            NOW + timedelta(seconds=1)
        ),
    )

    created_second = membership_store.create(
        second_membership
    )

    assert created_second.role is None
    assert created_second.revision == 0

    promoted_second = (
        membership_store.transition_role(
            created_second.membership_id,
            new_role="admin",
            changed_at=(
                NOW + timedelta(seconds=2)
            ),
            expected_revision=0,
            changed_by_principal_id=(
                PRINCIPAL_A
            ),
            reason=(
                "establish second active manager"
            ),
        )
    )

    assert (
        promoted_second.membership.role
        == "admin"
    )
    assert (
        promoted_second.membership.revision
        == 1
    )

    changed = membership_store.transition_status(
        provisioned.membership.membership_id,
        new_status="suspended",
        changed_at=(
            NOW + timedelta(seconds=3)
        ),
        expected_revision=1,
        changed_by_principal_id=(
            PRINCIPAL_B
        ),
        reason="temporary suspension",
    )

    assert changed.membership.status == (
        "suspended"
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert discovered == []


def test_discovery_excludes_roleless_membership(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace = ProvisionedWorkspace(
        workspace_id=create_workspace_id(),
        created_at=NOW,
        updated_at=NOW,
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
                updated_at,
                workspace_kind
            )
            VALUES (?, ?, ?, 'provisioned')
            """,
            (
                workspace.workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=workspace.workspace_id,
    ).create(
        WorkspaceMembership(
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id=workspace.workspace_id,
            principal_id=PRINCIPAL_A,
            status="active",
            role=None,
            revision=0,
            created_by_principal_id=(
                PRINCIPAL_A
            ),
            created_at=NOW,
            updated_at=NOW,
            status_changed_at=NOW,
        )
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert discovered == []


def test_discovery_returns_empty_for_inactive_principal(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(
        path,
        PRINCIPAL_A,
        status="suspended",
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert discovered == []


def test_discovery_orders_by_membership_update_descending(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    first = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=NOW,
        )
    )

    second = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=(
                NOW + timedelta(seconds=1)
            ),
        )
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated(
                PRINCIPAL_A
            )
        )
    )

    assert [
        item.workspace_id
        for item in discovered
    ] == [
        second.workspace.workspace_id,
        first.workspace.workspace_id,
    ]


def test_discovery_requires_authenticated_principal(
    tmp_path: Path,
):
    path = _database(tmp_path)

    with pytest.raises(
        TypeError,
        match="authenticated request principal",
    ):
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=object()
        )
def test_discovery_applies_server_owned_result_ceiling(
    tmp_path: Path,
    monkeypatch,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    first = service.provision(
        principal_id=PRINCIPAL_A,
        created_at=NOW,
    )

    second = service.provision(
        principal_id=PRINCIPAL_A,
        created_at=(
            NOW + timedelta(seconds=1)
        ),
    )

    third = service.provision(
        principal_id=PRINCIPAL_A,
        created_at=(
            NOW + timedelta(seconds=2)
        ),
    )

    monkeypatch.setattr(
        workspace_discovery,
        "MAX_WORKSPACE_DISCOVERY_RESULTS",
        2,
    )

    discovered = (
        SQLiteWorkspaceDiscoveryService(
            path
        ).list_accessible(
            principal=_authenticated_principal(
                PRINCIPAL_A
            )
        )
    )

    assert len(discovered) == 2

    assert [
        item.workspace_id
        for item in discovered
    ] == [
        third.workspace.workspace_id,
        second.workspace.workspace_id,
    ]

    assert (
        first.workspace.workspace_id
        not in {
            item.workspace_id
            for item in discovered
        }
    )


def test_discovery_query_uses_principal_discovery_index_without_temp_sort(
    tmp_path: Path,
):
    path = _database(tmp_path)

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        rows = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                workspace.workspace_id,
                workspace.workspace_kind,
                workspace.created_at
                    AS workspace_created_at,
                workspace.updated_at
                    AS workspace_updated_at,
                membership.membership_id,
                membership.role
                    AS membership_role,
                membership.revision
                    AS membership_revision,
                membership.created_at
                    AS membership_created_at,
                membership.updated_at
                    AS membership_updated_at
            FROM principals AS principal
            JOIN workspace_memberships AS membership
                ON
                    membership.principal_id =
                        principal.principal_id
            JOIN workspaces AS workspace
                ON
                    workspace.workspace_id =
                        membership.workspace_id
            WHERE
                principal.principal_id = ?
                AND principal.status = 'active'
                AND membership.status = 'active'
                AND membership.role IS NOT NULL
            ORDER BY
                membership.updated_at DESC,
                membership.workspace_id ASC
            LIMIT ?
            """,
            (
                PRINCIPAL_A,
                500,
            ),
        ).fetchall()
    finally:
        connection.close()

    details = [
        str(row["detail"])
        for row in rows
    ]

    assert any(
        (
            "idx_workspace_memberships_principal_discovery"
            in detail
        )
        for detail in details
    )

    assert not any(
        "USE TEMP B-TREE FOR ORDER BY"
        in detail
        for detail in details
    )

