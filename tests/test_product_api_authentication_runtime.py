from __future__ import annotations

from fastapi.testclient import TestClient

from execution_evidence.authentication_runtime import (
    AuthenticationRuntime,
)
from product_api import (
    app,
    get_authentication_runtime,
    get_request_authenticator,
)


class DummyAuthenticator:
    pass


def _runtime(
    *,
    status="ready",
    authenticator=None,
    provider_ids=(
        "idp_123e4567-e89b-42d3-a456-426614174000",
    ),
    errors=(),
):
    if authenticator is None and status == "ready":
        authenticator = DummyAuthenticator()

    return AuthenticationRuntime(
        status=status,
        authenticator=authenticator,
        configured_provider_ids=provider_ids,
        errors=errors,
    )


def test_authentication_readiness_reports_ready_status_only():
    runtime = _runtime()

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/authentication/readiness"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
    }


def test_authentication_readiness_reports_misconfigured_status_only():
    runtime = _runtime(
        status="misconfigured",
        authenticator=None,
        provider_ids=(),
        errors=(
            "Interactive OIDC authentication is "
            "misconfigured.",
        ),
    )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/authentication/readiness"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "misconfigured",
    }


def test_authentication_readiness_does_not_disclose_runtime_diagnostics():
    runtime = _runtime(
        status="unavailable_storage",
        authenticator=None,
        provider_ids=(
            "idp_123e4567-e89b-42d3-a456-426614174000",
        ),
        errors=(
            "Durable principal resolution storage "
            "is unavailable.",
        ),
    )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/authentication/readiness"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "status": "unavailable_storage",
    }
    assert "configured_provider_ids" not in payload
    assert "errors" not in payload


def test_request_authenticator_fails_closed_when_runtime_not_ready():
    runtime = _runtime(
        status="misconfigured",
        authenticator=None,
        provider_ids=(),
        errors=(
            "Interactive OIDC authentication is "
            "misconfigured.",
        ),
    )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: runtime

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    "/v1/workspaces/workspace-one/"
                    "projects/project-test/"
                    "execution-evidence/events/lineage"
                )
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Request authentication runtime is "
        "temporarily unavailable."
    )


def test_get_request_authenticator_returns_shared_instance():
    authenticator = DummyAuthenticator()
    runtime = _runtime(
        authenticator=authenticator
    )

    result = get_request_authenticator(
        runtime=runtime
    )

    assert result is authenticator
