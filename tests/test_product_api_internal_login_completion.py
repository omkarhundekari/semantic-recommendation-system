from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import threading

import pytest
from fastapi.testclient import TestClient

from execution_evidence.oidc_token_verifier import (
    OIDCTokenInvalidError,
)
from execution_evidence.principal_provisioning import (
    PrincipalProvisioningAccessDenied,
    PrincipalProvisioningConfigurationError,
)
from execution_evidence.sqlite_login_session_store import (
    LoginSessionCreationDeniedError,
    LoginSessionStoreError,
    LoginTransactionAlreadyConsumedError,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)
from product_api import (
    SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
    SOLVYN_INTERNAL_LOGIN_SECRET_HEADER,
    app,
    get_interactive_login_token_verifier,
    get_login_session_store,
    get_principal_login_provisioning_service,
)


SECRET = (
    "test-only-internal-login-secret-"
    "0123456789abcdef0123456789abcdef"
)

PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)

ISSUER = "https://accounts.google.com"

IDENTITY = VerifiedOIDCIdentity(
    identity_provider_id=PROVIDER_ID,
    issuer=ISSUER,
    subject="google-subject-123",
)


class FakeLoginVerifier:
    def __init__(
        self,
        *,
        error=None,
    ):
        self.calls = []
        self.error = error

    def verify_login_id_token(
        self,
        token,
        *,
        expected_nonce,
    ):
        self.calls.append(
            (
                token,
                expected_nonce,
            )
        )

        if self.error is not None:
            raise self.error

        return IDENTITY


class FakeProvisioningService:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def resolve_or_provision(
        self,
        identity,
        *,
        now,
    ):
        self.calls.append(
            (
                identity,
                now,
            )
        )

        return self.result



class FakeLoginSessionStore:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def create_session_for_login_transaction(
        self,
        *,
        transaction_id,
        principal_id,
        identity_link_id,
        now,
    ):
        # Preserve the original test-double call contract:
        #
        #   0 -> transaction_id
        #   1 -> principal_id
        #   2 -> identity_link_id
        #   3 -> backend/server timestamp
        #
        # Existing tests intentionally inspect this tuple.
        self.calls.append(
            (
                transaction_id,
                principal_id,
                identity_link_id,
                now,
            )
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return SimpleNamespace(
            token=(
                "session-token-"
                "0123456789abcdef"
                "0123456789abcdef"
            ),
            session=SimpleNamespace(
                # Preserve the original fake behavior.
                # Tests use this to prove the server-derived
                # issuance timestamp flows through the response.
                expires_at=now,
            ),
        )


@pytest.fixture(autouse=True)
def clear_dependency_overrides(
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
    secret=SECRET,
):
    headers = {}

    if secret is not None:
        headers[
            SOLVYN_INTERNAL_LOGIN_SECRET_HEADER
        ] = secret

    return TestClient(app).post(
        "/internal/v1/auth/google/complete",
        headers=headers,
        json={
            "id_token": "signed-google-id-token",
            "expected_nonce": "expected-login-nonce",
            "transaction_id": (
                "transaction-"
                "0123456789abcdef0123456789abcdef"
            ),
        },
    )


def test_internal_login_verifies_nonce_and_provisions_once():
    verifier = FakeLoginVerifier()

    principal = SimpleNamespace(
        principal_id=(
            "prn_123e4567-e89b-42d3-a456-426614174001"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
    )

    provisioning = FakeProvisioningService(
        SimpleNamespace(
            status="existing",
            principal=principal,
        )
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 200

    assert response.json() == {
        "status": "existing",
        "principal_id": (
            principal.principal_id
        ),
        "identity_link_id": (
            principal.identity_link_id
        ),
        "session_token": (
            "session-token-"
            "0123456789abcdef0123456789abcdef"
        ),
        "session_expires_at": (
            session_store.calls[0][3]
            .isoformat()
        ),
    }

    assert verifier.calls == [
        (
            "signed-google-id-token",
            "expected-login-nonce",
        )
    ]

    assert len(provisioning.calls) == 1

    verified_identity, now = (
        provisioning.calls[0]
    )

    assert verified_identity == IDENTITY

    assert isinstance(
        now,
        datetime,
    )

    assert now.tzinfo is not None
    assert now.utcoffset() is not None


def test_internal_secret_is_required_before_token_verification():
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        None
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post(
        secret="wrong-secret-value",
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert verifier.calls == []
    assert provisioning.calls == []


def test_invalid_google_id_token_never_reaches_provisioning():
    verifier = FakeLoginVerifier(
        error=OIDCTokenInvalidError(
            "invalid token"
        )
    )

    provisioning = FakeProvisioningService(
        None
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert len(verifier.calls) == 1
    assert provisioning.calls == []


def test_access_denial_reason_is_not_exposed():
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        PrincipalProvisioningAccessDenied(
            reason="principal_suspended",
        )
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 401

    payload = response.json()

    assert payload == {
        "detail": "Authentication failed."
    }

    assert (
        "principal_suspended"
        not in response.text
    )

    assert len(provisioning.calls) == 1


def test_missing_internal_secret_configuration_is_503(
    monkeypatch,
):
    monkeypatch.delenv(
        SOLVYN_INTERNAL_LOGIN_SECRET_ENV,
        raising=False,
    )

    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        None
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    response = _post()

    assert response.status_code == 503

    assert verifier.calls == []
    assert provisioning.calls == []



def test_replayed_login_transaction_is_rejected():
    from execution_evidence.sqlite_login_session_store import (
        LoginTransactionAlreadyConsumedError,
    )

    verifier = FakeLoginVerifier()

    principal = SimpleNamespace(
        principal_id=(
            "prn_123e4567-e89b-42d3-a456-426614174001"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
    )

    provisioning = FakeProvisioningService(
        SimpleNamespace(
            status="existing",
            principal=principal,
        )
    )

    session_store = FakeLoginSessionStore(
        error=LoginTransactionAlreadyConsumedError(
            "already consumed"
        )
    )

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert len(session_store.calls) == 1

# === 1C-7B1 FINAL HARDENING TESTS ===


def _successful_principal():
    return SimpleNamespace(
        principal_id=(
            "prn_123e4567-e89b-42d3-a456-426614174001"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
    )


def _successful_provisioning_result():
    return SimpleNamespace(
        status="existing",
        principal=_successful_principal(),
    )


def _install_success_dependencies(
    *,
    session_store=None,
):
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        _successful_provisioning_result()
    )

    if session_store is None:
        session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    return (
        verifier,
        provisioning,
        session_store,
    )


def test_session_creation_failure_fails_closed():
    session_store = FakeLoginSessionStore(
        error=LoginSessionStoreError(
            "temporary session failure"
        )
    )

    (
        verifier,
        provisioning,
        _,
    ) = _install_success_dependencies(
        session_store=session_store
    )

    response = _post()

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Interactive authentication is "
            "temporarily unavailable."
        )
    }

    assert len(verifier.calls) == 1
    assert len(provisioning.calls) == 1
    assert len(session_store.calls) == 1


def test_session_creation_denial_fails_closed():
    session_store = FakeLoginSessionStore(
        error=LoginSessionCreationDeniedError(
            "inactive identity binding"
        )
    )

    (
        _,
        _,
        session_store,
    ) = _install_success_dependencies(
        session_store=session_store
    )

    response = _post()

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert len(session_store.calls) == 1


def test_replayed_login_transaction_is_uniform_401():
    session_store = FakeLoginSessionStore(
        error=LoginTransactionAlreadyConsumedError(
            "already consumed"
        )
    )

    (
        _,
        _,
        session_store,
    ) = _install_success_dependencies(
        session_store=session_store
    )

    response = _post()

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert (
        "already consumed"
        not in response.text
    )

    assert len(session_store.calls) == 1


@pytest.mark.parametrize(
    "reason",
    [
        "principal_suspended",
        "principal_deactivated",
        "identity_link_ended",
        "identity_provider_disabled",
        "identity_provider_mismatch",
        "identity_link_severed",
    ],
)
def test_every_access_denial_reason_blocks_session_issuance(
    reason,
):
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        PrincipalProvisioningAccessDenied(
            reason=reason,
        )
    )

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Authentication failed."
    }

    assert reason not in response.text
    assert len(provisioning.calls) == 1
    assert session_store.calls == []


def test_provisioning_configuration_error_never_issues_session():
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        None
    )

    def fail_configuration(
        identity,
        *,
        now,
    ):
        provisioning.calls.append(
            (
                identity,
                now,
            )
        )

        raise PrincipalProvisioningConfigurationError(
            "invalid provider configuration"
        )

    provisioning.resolve_or_provision = (
        fail_configuration
    )

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post()

    assert response.status_code == 503

    assert "invalid provider configuration" not in response.text

    assert len(provisioning.calls) == 1
    assert session_store.calls == []


def test_raw_session_token_is_not_exposed_in_error_response(
    monkeypatch,
):
    raw_token = (
        "session-token-"
        "0123456789abcdef"
        "0123456789abcdef"
    )

    session_store = FakeLoginSessionStore(
        result=SimpleNamespace(
            token=raw_token,
            session=SimpleNamespace(
                expires_at=datetime.fromisoformat(
                    "2026-08-23T22:00:00+00:00"
                ),
            ),
        )
    )

    (
        _,
        _,
        session_store,
    ) = _install_success_dependencies(
        session_store=session_store
    )

    response = _post()

    assert response.status_code == 200

    payload = response.json()

    assert payload["session_token"] == raw_token

    # The only intended appearance is the successful
    # protected BFF response field itself. No duplicate
    # token material should appear elsewhere.
    assert response.text.count(raw_token) == 1


def test_internal_secret_rejection_does_not_touch_session_store():
    verifier = FakeLoginVerifier()

    provisioning = FakeProvisioningService(
        None
    )

    session_store = FakeLoginSessionStore()

    app.dependency_overrides[
        get_interactive_login_token_verifier
    ] = lambda: verifier

    app.dependency_overrides[
        get_principal_login_provisioning_service
    ] = lambda: provisioning

    app.dependency_overrides[
        get_login_session_store
    ] = lambda: session_store

    response = _post(
        secret="wrong-secret-value",
    )

    assert response.status_code == 401

    assert verifier.calls == []
    assert provisioning.calls == []
    assert session_store.calls == []
