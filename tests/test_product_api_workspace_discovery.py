from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.workspace_discovery import (
    DiscoveredWorkspace,
    WorkspaceDiscoveryResult,
    WorkspaceDiscoveryStoreError,
)
from product_api import (
    app,
    get_product_authenticated_principal,
    get_workspace_discovery_service,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174031"
)

NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)


def _principal():
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-426614174032"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174033"
        ),
        issuer="https://issuer.example",
        subject="workspace-discovery-subject",
    )


def _workspace():
    return DiscoveredWorkspace(
        workspace_id=(
            "wsp_123e4567-e89b-42d3-a456-426614174034"
        ),
        workspace_kind="provisioned",
        membership_id=(
            "wsm_123e4567-e89b-42d3-a456-426614174035"
        ),
        membership_role="owner",
        membership_revision=1,
        workspace_created_at=NOW,
        workspace_updated_at=NOW,
        membership_created_at=NOW,
        membership_updated_at=NOW,
    )


class FakeDiscoveryService:
    def __init__(
        self,
        *,
        result=None,
        error=None,
        truncated=False,
    ):
        self.result = (
            []
            if result is None
            else result
        )
        self.error = error
        self.calls = []
        self.truncated = truncated

    def discover(
        self,
        *,
        principal,
    ):
        self.calls.append(principal)

        if self.error is not None:
            raise self.error

        return WorkspaceDiscoveryResult(
            workspaces=self.result,
            truncated=getattr(
                self,
                "truncated",
                False,
            ),
        )

    def list_accessible(
        self,
        *,
        principal,
    ):
        return self.discover(
            principal=principal
        ).workspaces


def _install(service):
    principal = _principal()

    app.dependency_overrides[
        get_product_authenticated_principal
    ] = lambda: principal

    app.dependency_overrides[
        get_workspace_discovery_service
    ] = lambda: service

    return principal


def test_authenticated_principal_can_discover_workspaces():
    discovered = _workspace()

    service = FakeDiscoveryService(
        result=[discovered]
    )

    principal = _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert (
        response.headers[
            "Workspace-Discovery-Truncated"
        ]
        == "false"
    )

    assert response.json() == [
        discovered.model_dump(
            mode="json"
        )
    ]

    assert service.calls == [principal]


def test_workspace_discovery_can_return_empty_list():
    service = FakeDiscoveryService(
        result=[]
    )

    _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []
    assert len(service.calls) == 1


def test_workspace_discovery_maps_store_failure_to_503():
    service = FakeDiscoveryService(
        error=WorkspaceDiscoveryStoreError(
            "storage failure"
        )
    )

    _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Workspace discovery is temporarily "
            "unavailable."
        )
    }


def test_workspace_discovery_maps_validation_failure_to_422():
    service = FakeDiscoveryService(
        error=ValueError(
            "Invalid discovery principal."
        )
    )

    _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Invalid discovery principal."
    }


def test_workspace_discovery_authentication_failure_prevents_store_access():
    service = FakeDiscoveryService(
        result=[_workspace()]
    )

    def authentication_failure():
        raise HTTPException(
            status_code=401,
            detail="Authentication failed.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    app.dependency_overrides[
        get_product_authenticated_principal
    ] = authentication_failure

    app.dependency_overrides[
        get_workspace_discovery_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"
    assert service.calls == []


def test_workspace_discovery_does_not_accept_principal_scope_from_query():
    service = FakeDiscoveryService(
        result=[]
    )

    principal = _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces",
                params={
                    "principal_id": (
                        "prn_123e4567-e89b-42d3-a456-426614174099"
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.calls == [principal]

def test_workspace_discovery_reports_server_truncation():
    discovered = _workspace()

    service = FakeDiscoveryService(
        result=[discovered],
        truncated=True,
    )

    _install(service)

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        discovered.model_dump(
            mode="json"
        )
    ]
    assert (
        response.headers[
            "Workspace-Discovery-Truncated"
        ]
        == "true"
    )
