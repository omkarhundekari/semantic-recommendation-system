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
    WorkspaceMembershipInactiveError,
    WorkspaceMembershipRevisionConflictError,
    WorkspaceMembershipRoleAuthorizationError,
    WorkspaceMembershipTransitionError,
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
WORKSPACE_ID = "workspace-role-admin-test"


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


def _setup(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)

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

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    principal_store = SQLitePrincipalStore(path)

    owner_id = create_principal_id()
    target_id = create_principal_id()

    principal_store.create(_principal(owner_id))
    principal_store.create(_principal(target_id))

    owner = store.create(_membership(owner_id))
    target = store.create(_membership(target_id))

    SQLiteWorkspaceOwnerBootstrapService(
        path
    ).bootstrap_first_owner(
        workspace_id=WORKSPACE_ID,
        membership_id=owner.membership_id,
        changed_at=LATER,
    )

    return (
        path,
        store,
        owner_id,
        target_id,
        owner,
        target,
    )


def test_list_current_memberships_includes_suspended_and_excludes_removed(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    store.transition_status(
        target.membership_id,
        new_status="suspended",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    current = store.list_current_memberships()

    ids = {
        membership.membership_id
        for membership in current
    }

    assert target.membership_id in ids

    suspended = next(
        membership
        for membership in current
        if membership.membership_id
        == target.membership_id
    )
    assert suspended.status == "suspended"

    store.transition_status(
        target.membership_id,
        new_status="removed",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=1,
        changed_by_principal_id=owner_id,
    )

    ids = {
        membership.membership_id
        for membership in store.list_current_memberships()
    }

    assert target.membership_id not in ids


def test_owner_can_assign_role_and_history_records_actor(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    result = store.transition_role(
        target.membership_id,
        new_role="member",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
        reason="Project contributor",
    )

    assert result.membership.role == "member"
    assert result.membership.revision == 1
    assert result.transition.previous_role is None
    assert result.transition.new_role == "member"
    assert (
        result.transition.changed_by_principal_id
        == owner_id
    )

    history = store.list_role_transitions(
        target.membership_id
    )

    assert len(history) == 1
    assert history[0] == result.transition


def test_role_transition_rejects_stale_revision(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    store.transition_role(
        target.membership_id,
        new_role="member",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipRevisionConflictError
    ):
        store.transition_role(
            target.membership_id,
            new_role="admin",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=0,
            changed_by_principal_id=owner_id,
        )


def test_role_and_status_share_one_revision_clock(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    store.transition_role(
        target.membership_id,
        new_role="member",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    status_result = store.transition_status(
        target.membership_id,
        new_status="suspended",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=1,
        changed_by_principal_id=owner_id,
    )

    assert status_result.membership.revision == 2


def test_role_transition_requires_active_target(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    store.transition_status(
        target.membership_id,
        new_status="suspended",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipInactiveError
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=1,
            changed_by_principal_id=owner_id,
        )


def test_role_transition_rejects_self_role_change(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        owner,
        _,
    ) = _setup(tmp_path)

    current_owner = store.load_by_id(
        owner.membership_id
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="own role",
    ):
        store.transition_role(
            current_owner.membership_id,
            new_role="admin",
            changed_at=LATER_TWO,
            expected_revision=current_owner.revision,
            changed_by_principal_id=owner_id,
        )


def test_non_owner_cannot_assign_owner(
    tmp_path: Path,
):
    (
        path,
        store,
        owner_id,
        target_id,
        _,
        target,
    ) = _setup(tmp_path)

    admin_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        _principal(admin_id)
    )

    admin = store.create(
        _membership(admin_id)
    )

    store.transition_role(
        admin.membership_id,
        new_role="admin",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="Only a workspace owner",
    ):
        store.transition_role(
            target.membership_id,
            new_role="owner",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=0,
            changed_by_principal_id=admin_id,
        )

    assert (
        store.load_by_id(target.membership_id).role
        is None
    )


def test_non_owner_cannot_revoke_owner(
    tmp_path: Path,
):
    (
        path,
        store,
        owner_id,
        _,
        owner,
        _,
    ) = _setup(tmp_path)

    admin_id = create_principal_id()
    second_owner_id = create_principal_id()

    principal_store = SQLitePrincipalStore(path)
    principal_store.create(_principal(admin_id))
    principal_store.create(
        _principal(second_owner_id)
    )

    admin = store.create(_membership(admin_id))
    second_owner = store.create(
        _membership(second_owner_id)
    )

    store.transition_role(
        admin.membership_id,
        new_role="admin",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    store.transition_role(
        second_owner.membership_id,
        new_role="owner",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    current_second_owner = store.load_by_id(
        second_owner.membership_id
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="Only a workspace owner",
    ):
        store.transition_role(
            current_second_owner.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=2)
            ),
            expected_revision=(
                current_second_owner.revision
            ),
            changed_by_principal_id=admin_id,
        )


def test_owner_can_assign_owner_to_another_member(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    result = store.transition_role(
        target.membership_id,
        new_role="owner",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    assert result.membership.role == "owner"


def test_role_transition_rejects_role_self_transition(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    first = store.transition_role(
        target.membership_id,
        new_role="member",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipTransitionError,
        match="self-transitions",
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=first.membership.revision,
            changed_by_principal_id=owner_id,
        )

def test_viewer_cannot_mutate_another_members_role(
    tmp_path: Path,
):
    (
        path,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    viewer_id = create_principal_id()
    principal_store = SQLitePrincipalStore(path)
    principal_store.create(_principal(viewer_id))

    viewer = store.create(_membership(viewer_id))

    store.transition_role(
        viewer.membership_id,
        new_role="viewer",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="workspace manager",
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=0,
            changed_by_principal_id=viewer_id,
        )


def test_unassigned_member_cannot_mutate_roles(
    tmp_path: Path,
):
    (
        path,
        store,
        _,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    actor_id = create_principal_id()

    SQLitePrincipalStore(path).create(
        _principal(actor_id)
    )

    actor = store.create(
        _membership(actor_id)
    )

    assert actor.role is None

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="workspace manager",
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=LATER_TWO,
            expected_revision=0,
            changed_by_principal_id=actor_id,
        )


def test_suspended_manager_cannot_mutate_roles(
    tmp_path: Path,
):
    (
        path,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    admin_id = create_principal_id()
    SQLitePrincipalStore(path).create(
        _principal(admin_id)
    )

    admin = store.create(_membership(admin_id))

    promoted = store.transition_role(
        admin.membership_id,
        new_role="admin",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    store.transition_status(
        promoted.membership.membership_id,
        new_status="suspended",
        changed_at=(
            LATER_TWO + timedelta(minutes=1)
        ),
        expected_revision=promoted.membership.revision,
        changed_by_principal_id=owner_id,
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="not active",
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=2)
            ),
            expected_revision=0,
            changed_by_principal_id=admin_id,
        )


def test_actor_from_other_workspace_cannot_mutate_role(
    tmp_path: Path,
):
    (
        path,
        store,
        _,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    other_workspace_id = "workspace-role-admin-other"
    other_owner_id = create_principal_id()

    principal_store = SQLitePrincipalStore(path)
    principal_store.create(_principal(other_owner_id))

    connection = connect_execution_evidence_database(path)

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
                other_workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    other_store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=other_workspace_id,
    )

    other_owner = other_store.create(
        WorkspaceMembership(
            membership_id=create_workspace_membership_id(),
            workspace_id=other_workspace_id,
            principal_id=other_owner_id,
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
        workspace_id=other_workspace_id,
        membership_id=other_owner.membership_id,
        changed_at=LATER,
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="current workspace member",
    ):
        store.transition_role(
            target.membership_id,
            new_role="member",
            changed_at=LATER_TWO,
            expected_revision=0,
            changed_by_principal_id=other_owner_id,
        )


def test_admin_cannot_demote_owner(
    tmp_path: Path,
):
    (
        path,
        store,
        owner_id,
        _,
        owner,
        _,
    ) = _setup(tmp_path)

    admin_id = create_principal_id()
    SQLitePrincipalStore(path).create(
        _principal(admin_id)
    )

    admin = store.create(_membership(admin_id))

    store.transition_role(
        admin.membership_id,
        new_role="admin",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    current_owner = store.load_by_id(
        owner.membership_id
    )

    with pytest.raises(
        WorkspaceMembershipRoleAuthorizationError,
        match="Only a workspace owner",
    ):
        store.transition_role(
            current_owner.membership_id,
            new_role="member",
            changed_at=(
                LATER_TWO + timedelta(minutes=1)
            ),
            expected_revision=current_owner.revision,
            changed_by_principal_id=admin_id,
        )


def test_role_history_is_ordered_by_resulting_revision(
    tmp_path: Path,
):
    (
        _,
        store,
        owner_id,
        _,
        _,
        target,
    ) = _setup(tmp_path)

    first = store.transition_role(
        target.membership_id,
        new_role="member",
        changed_at=LATER_TWO,
        expected_revision=0,
        changed_by_principal_id=owner_id,
    )

    second = store.transition_role(
        target.membership_id,
        new_role="admin",
        changed_at=(
            LATER_TWO + timedelta(minutes=2)
        ),
        expected_revision=first.membership.revision,
        changed_by_principal_id=owner_id,
    )

    history = store.list_role_transitions(
        target.membership_id
    )

    assert [
        transition.resulting_revision
        for transition in history
    ] == [
        first.transition.resulting_revision,
        second.transition.resulting_revision,
    ]
