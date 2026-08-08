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
