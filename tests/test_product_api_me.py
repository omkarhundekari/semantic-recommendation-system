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
    SOLVYN_BROWSER_SESSION_HEADER,
    SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
    SOLVYN_INTERNAL_LOGIN_SECRET_HEADER,
    app,
    get_authentication_runtime,
    get_execution_evidence_storage_runtime,
    get_principal_profile_reader,
    get_product_authenticated_principal,
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
        get_product_authenticated_principal
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
        get_product_authenticated_principal
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
        get_product_authenticated_principal
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
        get_product_authenticated_principal
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
        get_product_authenticated_principal
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
    assert "cookie" in vary
    assert (
        SOLVYN_BROWSER_SESSION_HEADER.lower()
        in vary
    )


def test_me_maps_internal_profile_validation_failure_to_503():
    reader = FakeProfileReader(
        error=ValueError(
            "internal principal validation detail"
        )
    )

    app.dependency_overrides[
        get_product_authenticated_principal
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
        get_product_authenticated_principal
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


# ============================================================
# 1D2 CONVERGED AUTHORITY ISOLATION
# ============================================================


class FakeBearerAuthenticator:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def authenticate(
        self,
        authorization,
    ):
        self.calls.append(
            authorization
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return authenticated_principal()


class FakeAuthenticationRuntime:
    def __init__(
        self,
        *,
        ready=True,
        authenticator=None,
    ):
        self.ready = ready
        self.authenticator = (
            authenticator
        )


class FakeTrustedSQLiteService:
    def __init__(
        self,
        path,
    ):
        self.path = path


class FakeStorageRuntime:
    def __init__(
        self,
        *,
        trusted_sqlite_service,
    ):
        self.trusted_sqlite_service = (
            trusted_sqlite_service
        )


def _direct_product_auth_request(
    *,
    authorization=None,
    session_token=None,
    internal_secret=None,
    origin=None,
):
    headers = {}

    if authorization is not None:
        headers["Authorization"] = (
            authorization
        )

    if session_token is not None:
        headers[
            SOLVYN_BROWSER_SESSION_HEADER
        ] = session_token

    if internal_secret is not None:
        headers[
            SOLVYN_INTERNAL_LOGIN_SECRET_HEADER
        ] = internal_secret

    if origin is not None:
        headers["Origin"] = origin

    return TestClient(
        app
    ).get(
        "/v1/me",
        headers=headers,
    )


def test_product_auth_bearer_path_survives_session_storage_unavailability():
    bearer = FakeBearerAuthenticator()

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: FakeAuthenticationRuntime(
        ready=True,
        authenticator=bearer,
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: FakeStorageRuntime(
        trusted_sqlite_service=None,
    )

    reader = FakeProfileReader()

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    response = _direct_product_auth_request(
        authorization="Bearer bearer-token",
    )

    assert response.status_code == 200

    assert bearer.calls == [
        "Bearer bearer-token"
    ]

    assert response.json() == {
        "principal_id": PRINCIPAL_ID,
        "principal_kind": "human",
    }


def test_product_auth_browser_session_path_survives_bearer_runtime_unavailability(
    tmp_path,
    monkeypatch,
):
    from datetime import (
        datetime,
        timezone,
    )

    from execution_evidence.sqlite_login_session_store import (
        SQLiteLoginSessionStore,
    )
    from execution_evidence.sqlite_schema import (
        CURRENT_SQLITE_SCHEMA_VERSION,
        connect_execution_evidence_database,
        initialize_execution_evidence_database,
    )

    database_path = (
        tmp_path / "product-auth-session.db"
    )

    assert (
        initialize_execution_evidence_database(
            database_path
        )
        == CURRENT_SQLITE_SCHEMA_VERSION
    )

    now = datetime(
        2026,
        8,
        17,
        21,
        0,
        tzinfo=timezone.utc,
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        timestamp = now.isoformat()

        connection.execute(
            """
            INSERT INTO identity_providers (
                identity_provider_id,
                provider_kind,
                issuer,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                'google',
                ?,
                'active',
                ?,
                ?
            )
            """,
            (
                PROVIDER_ID,
                "https://accounts.google.com",
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO principals (
                principal_id,
                principal_kind,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                'human',
                'active',
                ?,
                ?
            )
            """,
            (
                PRINCIPAL_ID,
                timestamp,
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO principal_identity_links (
                link_id,
                identity_provider_id,
                issuer,
                subject,
                principal_id,
                status,
                linked_at,
                ended_at,
                end_reason,
                ended_by_principal_id,
                severed_at,
                severed_reason,
                severed_by_principal_id
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                'active',
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL
            )
            """,
            (
                LINK_ID,
                PROVIDER_ID,
                "https://accounts.google.com",
                "google-subject-test",
                PRINCIPAL_ID,
                timestamp,
            ),
        )

    finally:
        connection.close()

    issued = SQLiteLoginSessionStore(
        database_path
    ).create_session(
        principal_id=PRINCIPAL_ID,
        identity_link_id=LINK_ID,
        now=now,
    )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: FakeAuthenticationRuntime(
        ready=False,
        authenticator=None,
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: FakeStorageRuntime(
        trusted_sqlite_service=(
            FakeTrustedSQLiteService(
                database_path
            )
        ),
    )

    reader = FakeProfileReader()

    app.dependency_overrides[
        get_principal_profile_reader
    ] = lambda: reader

    secret = (
        "test-only-internal-login-secret-"
        "0123456789abcdef0123456789abcdef"
    )

    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        secret,
    )

    response = _direct_product_auth_request(
        session_token=issued.token,
        internal_secret=secret,
    )

    assert response.status_code == 200

    assert response.json() == {
        "principal_id": PRINCIPAL_ID,
        "principal_kind": "human",
    }

    assert (
        response.headers[
            "cache-control"
        ]
        == "no-store"
    )

    vary = {
        value.strip().lower()
        for value
        in response.headers[
            "vary"
        ].split(",")
    }

    assert "authorization" in vary
    assert "cookie" in vary
    assert (
        SOLVYN_BROWSER_SESSION_HEADER.lower()
        in vary
    )


def test_product_auth_rejects_ambiguous_bearer_and_browser_session():
    response = _direct_product_auth_request(
        authorization="Bearer bearer-token",
        session_token=(
            "session-token-"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }


def test_product_auth_rejects_browser_origin_session_credential(
    monkeypatch,
):
    secret = (
        "test-only-internal-login-secret-"
        "0123456789abcdef0123456789abcdef"
    )

    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        secret,
    )

    response = _direct_product_auth_request(
        session_token=(
            "session-token-"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        internal_secret=secret,
        origin="http://localhost:3000",
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Not found."
    }


def test_internal_secret_alone_cannot_authenticate():
    response = _direct_product_auth_request(
        internal_secret=(
            "test-only-internal-login-secret-"
            "0123456789abcdef0123456789abcdef"
        ),
    )

    assert response.status_code in {
        401,
        503,
    }

    # It must never authenticate merely because the
    # internal secret header is present.
    assert response.status_code != 200


def test_stale_browser_session_maps_to_uniform_401(
    tmp_path,
    monkeypatch,
):
    from execution_evidence.sqlite_schema import (
        CURRENT_SQLITE_SCHEMA_VERSION,
        initialize_execution_evidence_database,
    )

    database_path = (
        tmp_path / "stale-session.db"
    )

    assert (
        initialize_execution_evidence_database(
            database_path
        )
        == CURRENT_SQLITE_SCHEMA_VERSION
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: FakeStorageRuntime(
        trusted_sqlite_service=(
            FakeTrustedSQLiteService(
                database_path
            )
        ),
    )

    secret = (
        "test-only-internal-login-secret-"
        "0123456789abcdef0123456789abcdef"
    )

    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        secret,
    )

    response = _direct_product_auth_request(
        session_token=(
            "session-token-"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        internal_secret=secret,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }


def test_browser_session_storage_outage_maps_to_503(
    monkeypatch,
):
    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: FakeStorageRuntime(
        trusted_sqlite_service=None,
    )

    secret = (
        "test-only-internal-login-secret-"
        "0123456789abcdef0123456789abcdef"
    )

    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        secret,
    )

    response = _direct_product_auth_request(
        session_token=(
            "session-token-"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        internal_secret=secret,
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Request authentication is temporarily "
            "unavailable."
        )
    }
