from __future__ import annotations

from fastapi.testclient import TestClient

from product_api import (
    SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
    SOLVYN_INTERNAL_LOGIN_SECRET_HEADER,
    app,
)


SECRET = (
    "test-only-internal-login-secret-"
    "0123456789abcdef0123456789abcdef"
)


def _headers(
    *,
    origin=None,
    preflight_method=None,
):
    headers = {
        SOLVYN_INTERNAL_LOGIN_SECRET_HEADER:
            SECRET,
    }

    if origin is not None:
        headers["Origin"] = origin

    if preflight_method is not None:
        headers[
            "Access-Control-Request-Method"
        ] = preflight_method

    return headers


def test_internal_session_resolve_rejects_browser_origin(
    monkeypatch,
):
    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SECRET,
    )

    response = TestClient(app).post(
        "/internal/v1/auth/session/resolve",
        headers=_headers(
            origin="http://localhost:3000",
        ),
        json={
            "session_token":
                "session-token-"
                "0123456789abcdef"
                "0123456789abcdef",
        },
    )

    assert response.status_code == 404


def test_internal_session_revoke_rejects_browser_origin(
    monkeypatch,
):
    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SECRET,
    )

    response = TestClient(app).post(
        "/internal/v1/auth/session/revoke",
        headers=_headers(
            origin="http://localhost:3000",
        ),
        json={
            "session_token":
                "session-token-"
                "0123456789abcdef"
                "0123456789abcdef",
        },
    )

    assert response.status_code == 404


def test_internal_google_completion_rejects_browser_origin(
    monkeypatch,
):
    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SECRET,
    )

    response = TestClient(app).post(
        "/internal/v1/auth/google/complete",
        headers=_headers(
            origin="http://localhost:3000",
        ),
        json={
            "id_token": "not-a-real-token",
            "expected_nonce": "nonce-value",
            "transaction_id":
                "transaction-"
                "0123456789abcdef"
                "0123456789abcdef",
        },
    )

    assert response.status_code == 404


def test_internal_auth_rejects_cors_preflight_context(
    monkeypatch,
):
    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SECRET,
    )

    response = TestClient(app).post(
        "/internal/v1/auth/session/resolve",
        headers=_headers(
            preflight_method="POST",
        ),
        json={
            "session_token":
                "session-token-"
                "0123456789abcdef"
                "0123456789abcdef",
        },
    )

    assert response.status_code == 404


def test_invalid_internal_secret_is_not_principal_authentication_failure(
    monkeypatch,
):
    """BFF channel rejection must never masquerade as stale user auth."""

    from fastapi.testclient import TestClient

    from product_api import (
        SOLVYN_BROWSER_SESSION_HEADER,
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SOLVYN_INTERNAL_LOGIN_SECRET_HEADER,
        app,
    )

    configured_secret = (
        "configured-internal-secret-"
        "0123456789abcdef0123456789abcdef"
    )

    wrong_secret = (
        "wrong-internal-secret-value-"
        "0123456789abcdef0123456789abcdef"
    )

    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        configured_secret,
    )

    response = TestClient(
        app
    ).get(
        "/v1/me",
        headers={
            SOLVYN_BROWSER_SESSION_HEADER: (
                "session-token-"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
            SOLVYN_INTERNAL_LOGIN_SECRET_HEADER:
                wrong_secret,
        },
    )

    assert response.status_code == 403

    assert response.status_code != 401

    assert response.json() == {
        "detail": "Authentication failed."
    }
