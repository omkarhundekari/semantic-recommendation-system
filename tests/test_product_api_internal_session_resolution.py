from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from execution_evidence.sqlite_login_session_store import (
    LoginSessionNotFoundError,
    LoginSessionStoreError,
)
from product_api import (
    SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
    SOLVYN_INTERNAL_LOGIN_SECRET_HEADER,
    app,
    get_login_session_store,
)


SECRET = (
    "test-only-internal-login-secret-"
    "0123456789abcdef0123456789abcdef"
)

TOKEN = (
    "session-token-"
    "0123456789abcdef"
    "0123456789abcdef"
)

NOW = datetime(
    2026,
    8,
    16,
    23,
    0,
    tzinfo=timezone.utc,
)


class FakeSessionStore:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def resolve_session(
        self,
        token,
        *,
        now,
    ):
        self.calls.append(
            (
                token,
                now,
            )
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return SimpleNamespace(
            session_id=(
                "ses_123e4567-e89b-42d3-"
                "a456-426614174000"
            ),
            principal_id=(
                "prn_123e4567-e89b-42d3-"
                "a456-426614174001"
            ),
            identity_link_id=(
                "pil_123e4567-e89b-42d3-"
                "a456-426614174002"
            ),
            expires_at=(
                datetime.fromisoformat(
                    "2026-08-23T23:00:00+00:00"
                )
            ),
        )


@pytest.fixture(autouse=True)
def clear_dependencies(
    monkeypatch,
):
    monkeypatch.setenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        SECRET,
    )

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


def _post(
    *,
    token=TOKEN,
    secret=SECRET,
):
    headers = {}

    if secret is not None:
        headers[
            SOLVYN_INTERNAL_LOGIN_SECRET_HEADER
        ] = secret

    return TestClient(app).post(
        "/internal/v1/auth/session/resolve",
        headers=headers,
        json={
            "session_token":
                token,
        },
    )


def test_active_session_resolves_read_only():
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "principal_id": (
            "prn_123e4567-e89b-42d3-"
            "a456-426614174001"
        ),
        "identity_link_id": (
            "pil_123e4567-e89b-42d3-"
            "a456-426614174002"
        ),
        "session_id": (
            "ses_123e4567-e89b-42d3-"
            "a456-426614174000"
        ),
        "session_expires_at":
            "2026-08-23T23:00:00+00:00",
    }

    assert TOKEN not in response.text

    assert len(store.calls) == 1

    resolved_token, now = (
        store.calls[0]
    )

    assert resolved_token == TOKEN

    assert isinstance(
        now,
        datetime,
    )

    assert now.tzinfo is not None
    assert now.utcoffset() is not None


def test_wrong_internal_secret_rejected_before_store_resolution():
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post(
        secret="wrong-secret",
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert store.calls == []


def test_missing_internal_secret_rejected_before_store_resolution():
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post(
        secret=None,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert store.calls == []


@pytest.mark.parametrize(
    "token",
    [
        "",
        " ",
        "short-token",
        (
            " session-token-"
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        (
            "session-token-"
            "0123456789abcdef"
            "0123456789abcdef "
        ),
        "x" * 1025,
    ],
)
def test_invalid_session_token_is_uniform_401(
    token,
):
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post(
        token=token,
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert store.calls == []


def test_inactive_session_is_uniform_401():
    store = FakeSessionStore(
        error=LoginSessionNotFoundError(
            "expired/revoked/inactive"
        )
    )

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert (
        "expired"
        not in response.text
    )

    assert (
        "revoked"
        not in response.text
    )

    assert (
        "inactive"
        not in response.text
    )

    assert len(store.calls) == 1


def test_session_store_outage_is_503_without_token_leak():
    store = FakeSessionStore(
        error=LoginSessionStoreError(
            "database unavailable"
        )
    )

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Session authentication is "
            "temporarily unavailable."
        )
    }

    assert TOKEN not in response.text

    assert len(store.calls) == 1


def test_session_resolution_never_echoes_raw_credential():
    raw_token = (
        "credential-that-must-never-"
        "appear-in-response-0123456789abcdef"
    )

    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post(
        token=raw_token,
    )

    assert response.status_code == 200

    assert raw_token not in response.text

    payload = response.json()

    assert "session_token" not in payload
