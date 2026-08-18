from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import (
    TestClient,
)

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal_profile import (
    PrincipalProfile,
    PrincipalProfileNotFoundError,
    PrincipalProfileReadError,
)
from product_api import (
    app,
    get_authenticated_request_principal,
    get_principal_profile_reader,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-"
    "a456-426614174001"
)

PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-"
    "a456-426614174002"
)

LINK_ID = (
    "pil_123e4567-e89b-42d3-"
    "a456-426614174003"
)


def authenticated_principal():
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://accounts.google.com",
        subject="google-subject-test",
    )


class FakeProfileReader:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def read(
        self,
        principal_id,
    ):
        self.calls.append(
            principal_id
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return PrincipalProfile(
            principal_id=principal_id,
            principal_kind="human",
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


def test_me_returns_only_minimal_browser_safe_profile():
    reader = FakeProfileReader()

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 200

    assert response.json() == {
        "principal_id": PRINCIPAL_ID,
        "principal_kind": "human",
    }

    assert reader.calls == [
        PRINCIPAL_ID
    ]

    serialized = response.text

    assert PROVIDER_ID not in serialized
    assert LINK_ID not in serialized
    assert "google-subject-test" not in serialized
    assert "accounts.google.com" not in serialized
    assert "workspace" not in serialized.lower()
    assert "session" not in serialized.lower()


def test_me_does_not_accept_caller_supplied_principal_scope():
    reader = FakeProfileReader()

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        (
            "/v1/me?"
            "principal_id="
            "prn_123e4567-e89b-42d3-"
            "a456-426614174099"
        )
    )

    assert response.status_code == 200

    assert response.json()[
        "principal_id"
    ] == PRINCIPAL_ID

    assert reader.calls == [
        PRINCIPAL_ID
    ]


def test_me_maps_concurrent_principal_invalidation_to_401():
    reader = FakeProfileReader(
        error=(
            PrincipalProfileNotFoundError(
                "not active"
            )
        )
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )


def test_me_maps_profile_storage_failure_to_503():
    reader = FakeProfileReader(
        error=(
            PrincipalProfileReadError(
                "storage unavailable"
            )
        )
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Principal profile is temporarily "
            "unavailable."
        )
    }



def test_me_sets_principal_safe_cache_headers():
    reader = FakeProfileReader()

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 200

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )

    assert (
        response.headers[
            "pragma"
        ]
        == "no-cache"
    )

    vary = {
        value.strip().lower()
        for value
        in response.headers[
            "vary"
        ].split(",")
    }

    assert "authorization" in vary


def test_me_maps_internal_profile_validation_failure_to_503():
    reader = FakeProfileReader(
        error=ValueError(
            "internal principal validation detail"
        )
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = authenticated_principal

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Principal profile is temporarily "
            "unavailable."
        )
    }

    assert (
        "internal principal validation detail"
        not in response.text
    )



def test_me_authentication_failure_precedes_profile_reader():
    reader = FakeProfileReader()

    def reject_authentication():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail="Authentication is required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = reject_authentication

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = TestClient(
        app
    ).get(
        "/v1/me"
    )

    assert response.status_code == 401
    assert reader.calls == []


def test_me_has_no_mutating_http_methods():
    routes = [
        route
        for route in app.routes
        if getattr(
            route,
            "path",
            None,
        ) == "/v1/me"
    ]

    assert len(routes) == 1

    assert routes[0].methods == {
        "GET"
    }
