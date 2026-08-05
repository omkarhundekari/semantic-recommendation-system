from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest

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
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    create_workspace_membership_id,
)
from execution_evidence.workspace_owner_bootstrap import (
    SQLiteWorkspaceOwnerBootstrapService,
    WorkspaceOwnerAlreadyBootstrappedError,
    WorkspaceOwnerBootstrapEligibilityError,
    WorkspaceOwnerBootstrapNotFoundError,
)


NOW = datetime(
    2026,
    8,
    4,
    12,
    0,
    tzinfo=timezone.utc,
)


def _insert_workspace(
    path: Path,
    workspace_id: str = "workspace-one",
) -> None:
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
                workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _create_principal(
    path: Path,
    *,
    status: str = "active",
) -> str:
    principal_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status=status,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    return principal_id


def _create_membership(
    path: Path,
    *,
    workspace_id: str = "workspace-one",
    principal_id: str,
) -> WorkspaceMembership:
    membership = WorkspaceMembership(
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id=workspace_id,
        principal_id=principal_id,
        status="active",
        revision=0,
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )

    return SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=workspace_id,
    ).create(membership)


def _setup(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"

    initialize_execution_evidence_database(
        path
    )
    _insert_workspace(path)

    principal_id = _create_principal(path)

    membership = _create_membership(
        path,
        principal_id=principal_id,
    )

    return (
        path,
        principal_id,
        membership,
    )


def test_bootstraps_existing_active_membership(
    tmp_path: Path,
):
    path, principal_id, membership = _setup(
        tmp_path
    )

    changed_at = NOW + timedelta(seconds=1)

    result = (
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=changed_at,
            reason="  trusted bootstrap  ",
        )
    )

    assert result.membership.role == "owner"
    assert result.membership.revision == 1

    assert result.transition.principal_id == (
        principal_id
    )
    assert result.transition.previous_role is None
    assert result.transition.new_role == "owner"
    assert result.transition.previous_revision == 0
    assert result.transition.resulting_revision == 1
    assert (
        result.transition.changed_by_principal_id
        is None
    )
    assert result.transition.reason == (
        "trusted bootstrap"
    )


def test_bootstrap_consumes_current_revision(
    tmp_path: Path,
):
    path, _, membership = _setup(tmp_path)

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id="workspace-one",
    )

    suspended = store.transition_status(
        membership.membership_id,
        new_status="suspended",
        changed_at=NOW + timedelta(seconds=1),
        expected_revision=0,
    )

    active = store.transition_status(
        membership.membership_id,
        new_status="active",
        changed_at=NOW + timedelta(seconds=2),
        expected_revision=(
            suspended.membership.revision
        ),
    )

    assert active.membership.revision == 2
    assert active.membership.role is None

    result = (
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=3),
        )
    )

    assert (
        result.transition.previous_revision
        == 2
    )
    assert (
        result.transition.resulting_revision
        == 3
    )
    assert result.membership.revision == 3
    assert result.membership.role == "owner"


def test_bootstrap_requires_existing_workspace(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    with pytest.raises(
        WorkspaceOwnerBootstrapNotFoundError,
        match="Workspace does not exist",
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="missing-workspace",
            membership_id=(
                create_workspace_membership_id()
            ),
            changed_at=NOW,
        )


def test_bootstrap_requires_membership_in_exact_workspace(
    tmp_path: Path,
):
    path, _, membership = _setup(tmp_path)

    _insert_workspace(
        path,
        workspace_id="workspace-two",
    )

    with pytest.raises(
        WorkspaceOwnerBootstrapNotFoundError,
        match="membership does not exist",
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-two",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=1),
        )


@pytest.mark.parametrize(
    "status",
    [
        "suspended",
        "removed",
    ],
)
def test_bootstrap_requires_active_membership(
    tmp_path: Path,
    status: str,
):
    path, _, membership = _setup(tmp_path)

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id="workspace-one",
    )

    transitioned = store.transition_status(
        membership.membership_id,
        new_status=status,
        changed_at=NOW + timedelta(seconds=1),
        expected_revision=0,
    )

    assert transitioned.membership.status == status

    with pytest.raises(
        WorkspaceOwnerBootstrapEligibilityError,
        match="membership must be active",
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=2),
        )


@pytest.mark.parametrize(
    "status",
    [
        "suspended",
        "deactivated",
    ],
)
def test_bootstrap_requires_active_principal(
    tmp_path: Path,
    status: str,
):
    path = tmp_path / "solvyn.db"

    initialize_execution_evidence_database(
        path
    )
    _insert_workspace(path)

    principal_id = _create_principal(
        path,
        status=status,
    )

    membership = _create_membership(
        path,
        principal_id=principal_id,
    )

    with pytest.raises(
        WorkspaceOwnerBootstrapEligibilityError,
        match="principal must be active",
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=1),
        )


def test_repeated_bootstrap_is_explicitly_rejected(
    tmp_path: Path,
):
    path, _, membership = _setup(tmp_path)

    service = (
        SQLiteWorkspaceOwnerBootstrapService(
            path
        )
    )

    service.bootstrap_first_owner(
        workspace_id="workspace-one",
        membership_id=membership.membership_id,
        changed_at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(
        WorkspaceOwnerAlreadyBootstrappedError,
        match="already has",
    ):
        service.bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=2),
        )


@pytest.mark.parametrize(
    "blocking_role",
    [
        "owner",
        "admin",
    ],
)
def test_existing_manager_role_blocks_bootstrap(
    tmp_path: Path,
    blocking_role: str,
):
    path, _, membership = _setup(tmp_path)

    other_principal = _create_principal(path)

    other_membership = _create_membership(
        path,
        principal_id=other_principal,
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT
                membership_row_id,
                revision
            FROM workspace_memberships
            WHERE membership_id = ?
            """,
            (
                other_membership.membership_id,
            ),
        ).fetchone()

        connection.execute(
            """
            INSERT INTO
                workspace_membership_role_transitions (
                    role_transition_id,
                    membership_row_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_role,
                    new_role,
                    previous_revision,
                    resulting_revision,
                    changed_at,
                    changed_by_principal_id,
                    reason
                )
            VALUES (
                ?, ?, ?, ?, ?, NULL, ?, 0, 1, ?, NULL, ?
            )
            """,
            (
                (
                    "wmr_123e4567-e89b-42d3-"
                    "a456-426614174000"
                ),
                int(row["membership_row_id"]),
                other_membership.membership_id,
                "workspace-one",
                other_principal,
                blocking_role,
                (
                    NOW
                    + timedelta(seconds=1)
                ).isoformat(),
                "existing manager",
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        WorkspaceOwnerAlreadyBootstrappedError,
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=2),
        )


def test_member_role_does_not_claim_initial_ownership(
    tmp_path: Path,
):
    path, principal_id, membership = _setup(
        tmp_path
    )

    other_principal = _create_principal(path)

    other_membership = _create_membership(
        path,
        principal_id=other_principal,
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT membership_row_id
            FROM workspace_memberships
            WHERE membership_id = ?
            """,
            (
                other_membership.membership_id,
            ),
        ).fetchone()

        connection.execute(
            """
            INSERT INTO
                workspace_membership_role_transitions (
                    role_transition_id,
                    membership_row_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_role,
                    new_role,
                    previous_revision,
                    resulting_revision,
                    changed_at,
                    changed_by_principal_id,
                    reason
                )
            VALUES (
                ?, ?, ?, ?, ?, NULL, 'member',
                0, 1, ?, NULL, ?
            )
            """,
            (
                (
                    "wmr_123e4567-e89b-42d3-"
                    "a456-426614174001"
                ),
                int(row["membership_row_id"]),
                other_membership.membership_id,
                "workspace-one",
                other_principal,
                (
                    NOW
                    + timedelta(seconds=1)
                ).isoformat(),
                "ordinary member",
            ),
        )
    finally:
        connection.close()

    result = (
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=NOW + timedelta(seconds=2),
        )
    )

    assert result.membership.principal_id == (
        principal_id
    )
    assert result.membership.role == "owner"


def test_bootstrap_does_not_create_workspace(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"

    initialize_execution_evidence_database(
        path
    )

    with pytest.raises(
        WorkspaceOwnerBootstrapNotFoundError,
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=(
                create_workspace_membership_id()
            ),
            changed_at=NOW,
        )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM workspaces
            WHERE workspace_id = 'workspace-one'
            """
        ).fetchone()["count"]
    finally:
        connection.close()

    assert count == 0


def test_concurrent_bootstrap_produces_one_owner(
    tmp_path: Path,
):
    path, _, first = _setup(tmp_path)

    second_principal = _create_principal(path)

    second = _create_membership(
        path,
        principal_id=second_principal,
    )

    barrier = Barrier(2)

    def bootstrap(membership_id: str):
        barrier.wait()

        try:
            result = (
                SQLiteWorkspaceOwnerBootstrapService(
                    path
                ).bootstrap_first_owner(
                    workspace_id="workspace-one",
                    membership_id=membership_id,
                    changed_at=(
                        NOW
                        + timedelta(seconds=1)
                    ),
                )
            )
            return (
                "success",
                result.membership.membership_id,
            )
        except (
            WorkspaceOwnerAlreadyBootstrappedError
        ):
            return (
                "already_bootstrapped",
                membership_id,
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as pool:
        outcomes = list(
            pool.map(
                bootstrap,
                (
                    first.membership_id,
                    second.membership_id,
                ),
            )
        )

    assert sorted(
        outcome[0]
        for outcome in outcomes
    ) == [
        "already_bootstrapped",
        "success",
    ]

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        owners = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM workspace_memberships
            WHERE
                workspace_id = 'workspace-one'
                AND status = 'active'
                AND role = 'owner'
            """
        ).fetchone()["count"]

        role_rows = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM workspace_membership_role_transitions
            WHERE
                workspace_id = 'workspace-one'
                AND new_role = 'owner'
            """
        ).fetchone()["count"]
    finally:
        connection.close()

    assert owners == 1
    assert role_rows == 1


def test_bootstrap_requires_timezone_aware_timestamp(
    tmp_path: Path,
):
    path, _, membership = _setup(tmp_path)

    naive = datetime(
        2026,
        8,
        4,
        12,
        0,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id="workspace-one",
            membership_id=membership.membership_id,
            changed_at=naive,
        )
