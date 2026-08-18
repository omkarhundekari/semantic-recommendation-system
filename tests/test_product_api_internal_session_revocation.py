from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)

import pytest
from fastapi.testclient import TestClient

from execution_evidence.sqlite_login_session_store import (
    LoginSessionNotFoundError,
    LoginSessionStoreError,
    LoginSessionTransitionError,
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


class FakeSessionStore:
    def __init__(
        self,
        *,
        error=None,
    ):
        self.error = error
        self.calls = []

    def revoke_session(
        self,
        token,
        *,
        now,
        reason,
    ):
        self.calls.append(
            (
                token,
                now,
                reason,
            )
        )

        if self.error is not None:
            raise self.error

        return None


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
        "/internal/v1/auth/session/revoke",
        headers=headers,
        json={
            "session_token":
                token,
        },
    )


def test_active_session_is_revoked_without_exposing_state():
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 204
    assert response.content == b""

    assert len(store.calls) == 1

    token, now, reason = (
        store.calls[0]
    )

    assert token == TOKEN
    assert reason == "logout"

    assert isinstance(
        now,
        datetime,
    )

    assert now.tzinfo is not None
    assert now.utcoffset() is not None

    assert TOKEN not in response.text


def test_missing_session_is_idempotent_success():
    store = FakeSessionStore(
        error=LoginSessionNotFoundError(
            "missing session"
        )
    )

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 204
    assert response.content == b""
    assert len(store.calls) == 1


def test_already_revoked_session_is_idempotent_success():
    store = FakeSessionStore(
        error=LoginSessionTransitionError(
            "already revoked"
        )
    )

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post()

    assert response.status_code == 204
    assert response.content == b""

    assert (
        "already revoked"
        not in response.text
    )


def test_malformed_session_token_is_idempotent_success():
    class ValidatingFakeSessionStore(
        FakeSessionStore
    ):
        def revoke_session(
            self,
            token,
            *,
            now,
            reason,
        ):
            self.calls.append(
                (
                    token,
                    now,
                    reason,
                )
            )

            raise ValueError(
                "Login session token is invalid."
            )

    store = ValidatingFakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = _post(
        token="bad-token",
    )

    assert response.status_code == 204
    assert response.content == b""

    assert (
        "invalid"
        not in response.text.lower()
    )


def test_storage_failure_is_503_and_not_success():
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
        "detail":
            "Session logout is temporarily unavailable."
    }

    assert TOKEN not in response.text
    assert len(store.calls) == 1


def test_wrong_internal_secret_rejected_before_revocation():
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


def test_missing_internal_secret_rejected_before_revocation():
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


def test_extra_request_fields_are_rejected():
    store = FakeSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: store

    response = TestClient(app).post(
        "/internal/v1/auth/session/revoke",
        headers={
            SOLVYN_INTERNAL_LOGIN_SECRET_HEADER:
                SECRET,
        },
        json={
            "session_token":
                TOKEN,
            "principal_id":
                "prn_client_supplied_forbidden",
        },
    )

    assert response.status_code == 422
    assert store.calls == []
