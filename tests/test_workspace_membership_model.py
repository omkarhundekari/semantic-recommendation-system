from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipRoleTransition,
    WorkspaceMembershipTransition,
    create_workspace_membership_id,
    create_workspace_membership_role_transition_id,
    create_workspace_membership_transition_id,
)


NOW = datetime(
    2026,
    8,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)


def _membership(
    **updates,
) -> WorkspaceMembership:
    values = {
        "membership_id": (
            create_workspace_membership_id()
        ),
        "workspace_id": "workspace-test",
        "principal_id": "prn_test",
        "status": "active",
        "revision": 0,
        "created_by_principal_id": None,
        "created_at": NOW,
        "updated_at": NOW,
        "status_changed_at": NOW,
    }
    values.update(updates)
    return WorkspaceMembership(**values)


def test_membership_id_is_random_uuid4():
    first = create_workspace_membership_id()
    second = create_workspace_membership_id()

    assert first != second
    assert first.startswith("wsm_")
    assert second.startswith("wsm_")


def test_transition_id_is_random_uuid4():
    first = (
        create_workspace_membership_transition_id()
    )
    second = (
        create_workspace_membership_transition_id()
    )

    assert first != second
    assert first.startswith("wmt_")
    assert second.startswith("wmt_")


def test_role_transition_id_is_random_uuid4():
    first = (
        create_workspace_membership_role_transition_id()
    )
    second = (
        create_workspace_membership_role_transition_id()
    )

    assert first != second
    assert first.startswith("wmr_")
    assert second.startswith("wmr_")


def test_membership_role_is_unassigned_by_default():
    membership = _membership()

    assert membership.role is None


def test_role_transition_rejects_noncanonical_id():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        WorkspaceMembershipRoleTransition(
            transition_id=(
                "wmr_00000000-0000-1000-"
                "8000-000000000001"
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_role=None,
            new_role="owner",
            previous_revision=0,
            resulting_revision=1,
            changed_at=NOW,
        )


def test_role_transition_assigns_first_role_after_genesis():
    transition = WorkspaceMembershipRoleTransition(
        transition_id=(
            create_workspace_membership_role_transition_id()
        ),
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_role=None,
        new_role="owner",
        previous_revision=0,
        resulting_revision=1,
        changed_at=NOW,
        changed_by_principal_id=None,
    )

    assert transition.previous_role is None
    assert transition.new_role == "owner"
    assert transition.previous_revision == 0
    assert transition.resulting_revision == 1
    assert transition.changed_by_principal_id is None


def test_role_transition_requires_concrete_new_role():
    with pytest.raises(ValidationError):
        WorkspaceMembershipRoleTransition(
            transition_id=(
                create_workspace_membership_role_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_role=None,
            new_role=None,
            previous_revision=0,
            resulting_revision=1,
            changed_at=NOW,
        )


def test_role_transition_rejects_self_transition():
    with pytest.raises(
        ValidationError,
        match="self-transitions",
    ):
        WorkspaceMembershipRoleTransition(
            transition_id=(
                create_workspace_membership_role_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_role="member",
            new_role="member",
            previous_revision=2,
            resulting_revision=3,
            changed_at=NOW,
        )


def test_role_transition_rejects_revision_jump():
    with pytest.raises(
        ValidationError,
        match="advance exactly once",
    ):
        WorkspaceMembershipRoleTransition(
            transition_id=(
                create_workspace_membership_role_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_role=None,
            new_role="owner",
            previous_revision=0,
            resulting_revision=2,
            changed_at=NOW,
        )


def test_role_transition_requires_timezone_aware_time():
    naive = datetime(
        2026,
        8,
        2,
        12,
        0,
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        WorkspaceMembershipRoleTransition(
            transition_id=(
                create_workspace_membership_role_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_role=None,
            new_role="owner",
            previous_revision=0,
            resulting_revision=1,
            changed_at=naive,
        )


def test_role_transition_reason_is_normalized():
    transition = WorkspaceMembershipRoleTransition(
        transition_id=(
            create_workspace_membership_role_transition_id()
        ),
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_role=None,
        new_role="owner",
        previous_revision=0,
        resulting_revision=1,
        changed_at=NOW,
        reason="  trusted bootstrap  ",
    )

    assert transition.reason == "trusted bootstrap"


def test_membership_rejects_noncanonical_id():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _membership(
            membership_id=(
                "wsm_00000000-0000-1000-"
                "8000-000000000001"
            )
        )


def test_membership_rejects_identity_whitespace():
    with pytest.raises(
        ValidationError,
        match="surrounding whitespace",
    ):
        _membership(
            workspace_id=" workspace-test"
        )


def test_membership_requires_timezone_aware_dates():
    naive = datetime(
        2026,
        8,
        2,
        12,
        0,
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _membership(
            updated_at=naive
        )


def test_membership_created_at_requires_utc():
    non_utc = datetime(
        2026,
        8,
        2,
        8,
        0,
        tzinfo=timezone(
            -timedelta(hours=4)
        ),
    )

    with pytest.raises(
        ValidationError,
        match="created_at must use UTC",
    ):
        _membership(
            created_at=non_utc,
            updated_at=non_utc,
            status_changed_at=non_utc,
        )


def test_membership_rejects_invalid_timestamp_order():
    earlier = datetime(
        2026,
        8,
        1,
        12,
        0,
        tzinfo=timezone.utc,
    )

    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _membership(
            updated_at=earlier
        )


def test_genesis_transition_contract():
    membership_id = (
        create_workspace_membership_id()
    )

    transition = WorkspaceMembershipTransition(
        transition_id=(
            "wmt_genesis_" + membership_id
        ),
        membership_id=membership_id,
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_status=None,
        new_status="active",
        previous_revision=None,
        resulting_revision=0,
        changed_at=NOW,
    )

    assert transition.previous_status is None
    assert transition.resulting_revision == 0


def test_transition_revision_advances_once():
    transition = WorkspaceMembershipTransition(
        transition_id=(
            create_workspace_membership_transition_id()
        ),
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_status="active",
        new_status="suspended",
        previous_revision=3,
        resulting_revision=4,
        changed_at=NOW,
    )

    assert transition.resulting_revision == 4


def test_transition_rejects_revision_jump():
    with pytest.raises(
        ValidationError,
        match="advance exactly once",
    ):
        WorkspaceMembershipTransition(
            transition_id=(
                create_workspace_membership_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_status="active",
            new_status="suspended",
            previous_revision=3,
            resulting_revision=5,
            changed_at=NOW,
        )


def test_transition_rejects_self_transition():
    with pytest.raises(
        ValidationError,
        match="self-transitions",
    ):
        WorkspaceMembershipTransition(
            transition_id=(
                create_workspace_membership_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_status="active",
            new_status="active",
            previous_revision=0,
            resulting_revision=1,
            changed_at=NOW,
        )


@pytest.mark.parametrize(
    "previous_status,new_status",
    [
        ("active", "suspended"),
        ("active", "removed"),
        ("suspended", "active"),
        ("suspended", "removed"),
    ],
)
def test_allowed_membership_transitions(
    previous_status,
    new_status,
):
    WorkspaceMembershipTransition(
        transition_id=(
            create_workspace_membership_transition_id()
        ),
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_status=previous_status,
        new_status=new_status,
        previous_revision=0,
        resulting_revision=1,
        changed_at=NOW,
    )


@pytest.mark.parametrize(
    "new_status",
    [
        "active",
        "suspended",
    ],
)
def test_removed_membership_is_terminal(
    new_status,
):
    with pytest.raises(
        ValidationError,
        match="not allowed",
    ):
        WorkspaceMembershipTransition(
            transition_id=(
                create_workspace_membership_transition_id()
            ),
            membership_id=(
                create_workspace_membership_id()
            ),
            workspace_id="workspace-test",
            principal_id="prn_test",
            previous_status="removed",
            new_status=new_status,
            previous_revision=1,
            resulting_revision=2,
            changed_at=NOW,
        )


def test_transition_reason_is_normalized():
    transition = WorkspaceMembershipTransition(
        transition_id=(
            create_workspace_membership_transition_id()
        ),
        membership_id=(
            create_workspace_membership_id()
        ),
        workspace_id="workspace-test",
        principal_id="prn_test",
        previous_status="active",
        new_status="suspended",
        previous_revision=0,
        resulting_revision=1,
        changed_at=NOW,
        reason="  temporary hold  ",
    )

    assert transition.reason == "temporary hold"
