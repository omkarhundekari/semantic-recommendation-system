from fastapi.testclient import TestClient

from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.workspace_access_service import (
    WorkspaceAccessNotFoundError,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
)
from product_api import (
    app,
    get_authorized_workspace_context,
    get_authorized_workspace_membership_store,
)


WORKSPACE_ID = "workspace-membership-api-test"

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174001"
)

MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174002"
)


class FakeMembershipStore:
    def __init__(self):
        self.list_calls = 0

    def list_current_memberships(self):
        self.list_calls += 1
        return []


def _context(role):
    return AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role=role,
        workspace_id=WORKSPACE_ID,
    )


def test_manager_can_list_workspace_memberships():
    store = FakeMembershipStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/v1/workspaces/{WORKSPACE_ID}/memberships"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
    assert store.list_calls == 1


def test_viewer_cannot_list_workspace_memberships():
    store = FakeMembershipStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("viewer")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/v1/workspaces/{WORKSPACE_ID}/memberships"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert store.list_calls == 0


def test_inaccessible_workspace_is_404_before_roster_access():
    store = FakeMembershipStore()

    def inaccessible_context():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Workspace does not exist.",
        )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = inaccessible_context

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                f"/v1/workspaces/{WORKSPACE_ID}/memberships"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workspace does not exist."
    }
    assert store.list_calls == 0


def test_manager_can_read_workspace_membership_history():
    from datetime import datetime, timezone

    now = datetime(
        2026,
        8,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    membership = WorkspaceMembership(
        membership_id=MEMBERSHIP_ID,
        workspace_id=WORKSPACE_ID,
        principal_id=PRINCIPAL_ID,
        status="active",
        role="admin",
        revision=0,
        created_by_principal_id=None,
        created_at=now,
        updated_at=now,
        status_changed_at=now,
    )

    class HistoryStore:
        def __init__(self):
            self.calls = []

        def load_by_id(self, membership_id):
            self.calls.append(
                ("load", membership_id)
            )
            return membership

        def list_transitions(
            self,
            membership_id,
        ):
            self.calls.append(
                ("status", membership_id)
            )
            return []

        def list_role_transitions(
            self,
            membership_id,
        ):
            self.calls.append(
                ("role", membership_id)
            )
            return []

    store = HistoryStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("owner")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/history"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert (
        body["membership"]["membership_id"]
        == MEMBERSHIP_ID
    )
    assert body["status_transitions"] == []
    assert body["role_transitions"] == []

    assert store.calls == [
        ("load", MEMBERSHIP_ID),
        ("status", MEMBERSHIP_ID),
        ("role", MEMBERSHIP_ID),
    ]


def test_viewer_cannot_read_workspace_membership_history():
    class RecordingStore:
        def __init__(self):
            self.calls = []

        def load_by_id(self, membership_id):
            self.calls.append(
                ("load", membership_id)
            )
            raise AssertionError(
                "Membership storage must not run "
                "before capability authorization."
            )

    store = RecordingStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("viewer")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/history"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert store.calls == []


def test_missing_membership_history_is_404():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipNotFoundError,
    )

    class MissingMembershipStore:
        def __init__(self):
            self.calls = []

        def load_by_id(self, membership_id):
            self.calls.append(
                ("load", membership_id)
            )
            raise WorkspaceMembershipNotFoundError(
                "Workspace membership does not exist."
            )

    store = MissingMembershipStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/history"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Workspace membership does not exist."
        )
    }
    assert store.calls == [
        ("load", MEMBERSHIP_ID)
    ]


def test_inaccessible_workspace_is_404_before_history_access():
    class RecordingStore:
        def __init__(self):
            self.calls = []

        def load_by_id(self, membership_id):
            self.calls.append(
                ("load", membership_id)
            )
            raise AssertionError(
                "Membership storage must not run."
            )

    store = RecordingStore()

    def inaccessible_context():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Workspace does not exist.",
        )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = inaccessible_context

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/history"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workspace does not exist."
    }
    assert store.calls == []


def test_owner_can_transition_workspace_membership_role():
    from datetime import datetime, timezone

    from execution_evidence.workspace_membership import (
        WorkspaceMembershipRoleMutationResult,
        WorkspaceMembershipRoleTransition,
    )

    now = datetime(
        2026,
        8,
        7,
        12,
        0,
        tzinfo=timezone.utc,
    )

    target_principal_id = (
        "prn_123e4567-e89b-42d3-a456-426614174010"
    )
    target_membership_id = (
        "wsm_123e4567-e89b-42d3-a456-426614174011"
    )
    transition_id = (
        "wmr_123e4567-e89b-42d3-a456-426614174012"
    )

    membership = WorkspaceMembership(
        membership_id=target_membership_id,
        workspace_id=WORKSPACE_ID,
        principal_id=target_principal_id,
        status="active",
        role="member",
        revision=2,
        created_by_principal_id=None,
        created_at=now,
        updated_at=now,
        status_changed_at=now,
    )

    transition = WorkspaceMembershipRoleTransition(
        transition_id=transition_id,
        membership_id=target_membership_id,
        workspace_id=WORKSPACE_ID,
        principal_id=target_principal_id,
        previous_role="viewer",
        new_role="member",
        previous_revision=1,
        resulting_revision=2,
        changed_at=now,
        changed_by_principal_id=PRINCIPAL_ID,
        reason="promote member",
    )

    result = WorkspaceMembershipRoleMutationResult(
        membership=membership,
        transition=transition,
    )

    class RecordingStore:
        def __init__(self):
            self.calls = []

        def transition_role(
            self,
            membership_id,
            *,
            new_role,
            changed_at,
            expected_revision,
            changed_by_principal_id,
            reason=None,
        ):
            self.calls.append(
                {
                    "membership_id": membership_id,
                    "new_role": new_role,
                    "expected_revision": expected_revision,
                    "changed_by_principal_id": (
                        changed_by_principal_id
                    ),
                    "reason": reason,
                    "changed_at": changed_at,
                }
            )
            return result

    store = RecordingStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("owner")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{target_membership_id}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 1,
                    "reason": "promote member",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert (
        response.json()["membership"]["role"]
        == "member"
    )

    assert len(store.calls) == 1

    call = store.calls[0]

    assert (
        call["membership_id"]
        == target_membership_id
    )
    assert call["new_role"] == "member"
    assert call["expected_revision"] == 1
    assert (
        call["changed_by_principal_id"]
        == PRINCIPAL_ID
    )
    assert call["reason"] == "promote member"
    assert call["changed_at"].tzinfo is not None


def test_role_mutation_body_cannot_supply_actor():
    class RecordingStore:
        def __init__(self):
            self.calls = []

        def transition_role(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise AssertionError(
                "Store must not run for invalid request body."
            )

    store = RecordingStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("owner")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                    "changed_by_principal_id": (
                        PRINCIPAL_ID
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert store.calls == []


def test_member_without_role_manage_cannot_mutate_role():
    class RecordingStore:
        def __init__(self):
            self.calls = []

        def transition_role(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise AssertionError(
                "Store must not run before capability denial."
            )

    store = RecordingStore()

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("member")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "viewer",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert store.calls == []


def test_role_mutation_missing_membership_is_404():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipNotFoundError,
    )

    class MissingStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipNotFoundError(
                "Workspace membership does not exist."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: MissingStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workspace membership does not exist."
    }


def test_role_mutation_revision_conflict_is_409():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipRevisionConflictError,
    )

    class ConflictStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipRevisionConflictError(
                "Workspace membership revision conflict."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: ConflictStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_role_mutation_owner_protection_is_403():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipRoleAuthorizationError,
    )

    class AuthorizationStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipRoleAuthorizationError(
                "Only a workspace owner may assign "
                "or revoke the owner role."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: AuthorizationStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "owner",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_role_mutation_last_manager_is_409():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipLastManagerError,
    )

    class LastManagerStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipLastManagerError(
                "Workspace must retain at least one "
                "active owner or admin."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("owner")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: LastManagerStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_inaccessible_workspace_is_404_before_role_mutation():
    class RecordingStore:
        def __init__(self):
            self.calls = []

        def transition_role(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            raise AssertionError(
                "Role mutation storage must not run "
                "before workspace tenancy succeeds."
            )

    store = RecordingStore()

    def inaccessible_context():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail="Workspace does not exist.",
        )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = inaccessible_context

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: store

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workspace does not exist."
    }
    assert store.calls == []


def test_role_mutation_transition_conflict_is_409():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipTransitionError,
    )

    class TransitionConflictStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipTransitionError(
                "Workspace membership role transition "
                "is not allowed."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: TransitionConflictStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Workspace membership role transition "
            "is not allowed."
        )
    }


def test_role_mutation_inactive_target_is_409():
    from execution_evidence.workspace_membership_store import (
        WorkspaceMembershipInactiveError,
    )

    class InactiveStore:
        def transition_role(self, *args, **kwargs):
            raise WorkspaceMembershipInactiveError(
                "Workspace membership is not active."
            )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: _context("admin")

    app.dependency_overrides[
        get_authorized_workspace_membership_store
    ] = lambda: InactiveStore()

    try:
        with TestClient(app) as client:
            response = client.patch(
                (
                    f"/v1/workspaces/{WORKSPACE_ID}/"
                    f"memberships/{MEMBERSHIP_ID}/role"
                ),
                json={
                    "role": "member",
                    "expected_revision": 0,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Workspace membership is not active."
    }
