from datetime import datetime, timedelta, timezone
from pathlib import Path

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
from execution_evidence.workspace_membership_store import (
    WorkspaceMembershipLastManagerError,
)
from execution_evidence.workspace_owner_bootstrap import (
    SQLiteWorkspaceOwnerBootstrapService,
)


NOW = datetime(
    2026,
    8,
    7,
    12,
    0,
    tzinfo=timezone.utc,
)
LATER = NOW + timedelta(minutes=1)
LATER_TWO = NOW + timedelta(minutes=2)
WORKSPACE_ID = "workspace-last-manager-test"


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


def _membership(
    principal_id: str,
) -> WorkspaceMembership:
    return WorkspaceMembership(
        membership_id=create_workspace_membership_id(),
        workspace_id=WORKSPACE_ID,
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
):
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
                WORKSPACE_ID,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _setup_single_owner(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    _create_workspace(path)

    principal_store = SQLitePrincipalStore(path)
    owner_id = create_principal_id()
    principal_store.create(_principal(owner_id))

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    owner = store.create(
        _membership(owner_id)
    )

    bootstrapped = (
        SQLiteWorkspaceOwnerBootstrapService(
            path
        ).bootstrap_first_owner(
            workspace_id=WORKSPACE_ID,
            membership_id=owner.membership_id,
            changed_at=LATER,
        )
    )

    return (
        path,
        store,
        owner_id,
        bootstrapped.membership,
    )


def _add_admin(
    path: Path,
    store: SQLiteWorkspaceMembershipStore,
    *,
    owner_id: str,
):
    admin_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        _principal(admin_id)
    )

    admin = store.create(
        _membership(admin_id)
    )

    promoted = store.transition_role(
        admin.membership_id,
        new_role="admin",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    return admin_id, promoted.membership


def test_one_of_two_managers_can_be_demoted(
    tmp_path: Path,
):
    path, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    _, admin = _add_admin(
        path,
        store,
        owner_id=owner_id,
    )

    result = store.transition_role(
        admin.membership_id,
        new_role="member",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=admin.revision,
        changed_by_principal_id=owner_id,
    )

    assert result.membership.role == "member"

    remaining_owner = store.load_by_id(
        owner.membership_id
    )
    assert remaining_owner.role == "owner"
    assert remaining_owner.status == "active"


def test_last_manager_cannot_be_suspended(
    tmp_path: Path,
):
    _, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    with pytest.raises(
        WorkspaceMembershipLastManagerError
    ):
        store.transition_status(
            owner.membership_id,
            new_status="suspended",
            changed_at=LATER_TWO,
            expected_revision=owner.revision,
            changed_by_principal_id=owner_id,
        )


def test_last_manager_cannot_be_removed(
    tmp_path: Path,
):
    _, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    with pytest.raises(
        WorkspaceMembershipLastManagerError
    ):
        store.transition_status(
            owner.membership_id,
            new_status="removed",
            changed_at=LATER_TWO,
            expected_revision=owner.revision,
            changed_by_principal_id=owner_id,
        )


def test_manager_can_be_suspended_when_another_manager_exists(
    tmp_path: Path,
):
    path, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    _, admin = _add_admin(
        path,
        store,
        owner_id=owner_id,
    )

    result = store.transition_status(
        admin.membership_id,
        new_status="suspended",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=admin.revision,
        changed_by_principal_id=owner_id,
    )

    assert result.membership.status == "suspended"


def test_manager_can_be_removed_when_another_manager_exists(
    tmp_path: Path,
):
    path, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    _, admin = _add_admin(
        path,
        store,
        owner_id=owner_id,
    )

    result = store.transition_status(
        admin.membership_id,
        new_status="removed",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=admin.revision,
        changed_by_principal_id=owner_id,
    )

    assert result.membership.status == "removed"


def test_manager_can_be_demoted_when_another_manager_exists(
    tmp_path: Path,
):
    path, store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    _, admin = _add_admin(
        path,
        store,
        owner_id=owner_id,
    )

    result = store.transition_role(
        admin.membership_id,
        new_role="member",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=admin.revision,
        changed_by_principal_id=owner_id,
    )

    assert result.membership.role == "member"


def test_concurrent_mutual_removal_preserves_one_active_manager(
    tmp_path: Path,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    path, setup_store, owner_id, owner = (
        _setup_single_owner(tmp_path)
    )

    admin_id, admin = _add_admin(
        path,
        setup_store,
        owner_id=owner_id,
    )

    owner_before = setup_store.load_by_id(
        owner.membership_id
    )
    admin_before = setup_store.load_by_id(
        admin.membership_id
    )

    assert owner_before.status == "active"
    assert owner_before.role == "owner"
    assert admin_before.status == "active"
    assert admin_before.role == "admin"

    store_a = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )
    store_b = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    barrier = Barrier(2)

    def remove_other(
        store,
        *,
        target_membership_id,
        target_revision,
        actor_principal_id,
        changed_at,
    ):
        barrier.wait()

        try:
            result = store.transition_status(
                target_membership_id,
                new_status="removed",
                changed_at=changed_at,
                expected_revision=target_revision,
                changed_by_principal_id=(
                    actor_principal_id
                ),
                reason="concurrent manager removal",
            )
        except Exception as error:
            return ("error", error)

        return ("ok", result)

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        future_a = executor.submit(
            remove_other,
            store_a,
            target_membership_id=(
                admin_before.membership_id
            ),
            target_revision=admin_before.revision,
            actor_principal_id=owner_id,
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
        )
        future_b = executor.submit(
            remove_other,
            store_b,
            target_membership_id=(
                owner_before.membership_id
            ),
            target_revision=owner_before.revision,
            actor_principal_id=admin_id,
            changed_at=(
                LATER_TWO + timedelta(minutes=2)
            ),
        )

        outcomes = [
            future_a.result(),
            future_b.result(),
        ]

    successes = [
        value
        for kind, value in outcomes
        if kind == "ok"
    ]
    failures = [
        value
        for kind, value in outcomes
        if kind == "error"
    ]

    assert len(successes) == 1
    assert len(failures) == 1
    assert isinstance(
        failures[0],
        WorkspaceMembershipLastManagerError,
    )

    final_store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    owner_after = final_store.load_by_id(
        owner_before.membership_id
    )
    admin_after = final_store.load_by_id(
        admin_before.membership_id
    )

    memberships = [
        owner_after,
        admin_after,
    ]

    active_managers = [
        membership
        for membership in memberships
        if (
            membership.status == "active"
            and membership.role in {
                "owner",
                "admin",
            }
        )
    ]

    removed_managers = [
        membership
        for membership in memberships
        if membership.status == "removed"
    ]

    assert len(active_managers) == 1
    assert len(removed_managers) == 1

    survivor = active_managers[0]
    removed = removed_managers[0]

    original_revisions = {
        owner_before.membership_id:
            owner_before.revision,
        admin_before.membership_id:
            admin_before.revision,
    }

    assert (
        survivor.revision
        == original_revisions[
            survivor.membership_id
        ]
    )
    assert (
        removed.revision
        == original_revisions[
            removed.membership_id
        ] + 1
    )
