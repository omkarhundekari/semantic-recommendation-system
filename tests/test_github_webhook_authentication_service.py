import hashlib
import hmac
import json

import pytest

from execution_evidence.github_webhook_authentication_service import (
    GitHubWebhookAuthenticationService,
    GitHubWebhookAuthenticationStoreError,
    GitHubWebhookCredentialAuthorityNotFoundError,
    GitHubWebhookEndpointNotFoundError,
    GitHubWebhookRepositoryIdentityError,
    GitHubWebhookSecretResolutionError,
)
from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
)
from execution_evidence.github_webhook_credential_authority import (
    GitHubWebhookCredentialAuthority,
)
from execution_evidence.github_webhook_credential_authority_store import (
    GitHubWebhookCredentialAuthorityNotFoundError as StoreAuthorityNotFoundError,
    GitHubWebhookCredentialAuthorityStoreError,
)
from execution_evidence.github_webhook_credential_store import (
    GitHubWebhookCredentialNotFoundError,
    GitHubWebhookCredentialStoreError,
)
from execution_evidence.github_webhook_secret_resolver import (
    GitHubWebhookSecretNotFoundError,
)
from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
)


SECRET = b"github-per-source-secret"
ENDPOINT_ID = (
    "gwe_123e4567-e89b-42d3-a456-426614174000"
)
CREDENTIAL_ID = (
    "gwc_123e4567-e89b-42d3-a456-426614174000"
)
AUTHORITY_ID = (
    "gwa_123e4567-e89b-42d3-a456-426614174000"
)


def _credential():
    return GitHubWebhookCredential(
        github_webhook_credential_id=CREDENTIAL_ID,
        webhook_endpoint_id=ENDPOINT_ID,
        installation_id=None,
        secret_ref="SECRET_A",
        created_at="2026-08-03T20:00:00+00:00",
    )


def _authority():
    return GitHubWebhookCredentialAuthority(
        github_webhook_credential_authority_id=(
            AUTHORITY_ID
        ),
        github_webhook_credential_id=CREDENTIAL_ID,
        repository_id="123",
        created_at="2026-08-03T20:00:00+00:00",
    )


def _payload(
    repository_id=123,
):
    return {
        "repository": {
            "id": repository_id,
            "full_name": "owner/repo",
        }
    }


def _raw_body(
    repository_id=123,
):
    return json.dumps(
        _payload(repository_id),
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(raw_body):
    digest = hmac.new(
        SECRET,
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


class CredentialStore:
    def __init__(
        self,
        *,
        credential=None,
        error=None,
    ):
        self.credential = credential or _credential()
        self.error = error
        self.endpoint_ids = []

    def load_current_by_webhook_endpoint_id(
        self,
        webhook_endpoint_id,
    ):
        self.endpoint_ids.append(
            webhook_endpoint_id
        )

        if self.error is not None:
            raise self.error

        return self.credential


class AuthorityStore:
    def __init__(
        self,
        *,
        authority=None,
        error=None,
    ):
        self.authority = authority or _authority()
        self.error = error
        self.calls = []

    def load_current(
        self,
        *,
        github_webhook_credential_id,
        repository_id,
    ):
        self.calls.append(
            (
                github_webhook_credential_id,
                repository_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.authority


class SecretResolver:
    def __init__(
        self,
        *,
        secret=SECRET,
        error=None,
    ):
        self.secret = secret
        self.error = error
        self.secret_refs = []

    def resolve(self, secret_ref):
        self.secret_refs.append(secret_ref)

        if self.error is not None:
            raise self.error

        return self.secret


def _service(
    *,
    credential_store=None,
    authority_store=None,
    secret_resolver=None,
):
    return GitHubWebhookAuthenticationService(
        credential_store=(
            credential_store or CredentialStore()
        ),
        authority_store=(
            authority_store or AuthorityStore()
        ),
        secret_resolver=(
            secret_resolver or SecretResolver()
        ),
    )


def test_authenticates_exact_source():
    credential_store = CredentialStore()
    authority_store = AuthorityStore()
    secret_resolver = SecretResolver()

    service = _service(
        credential_store=credential_store,
        authority_store=authority_store,
        secret_resolver=secret_resolver,
    )

    raw_body = _raw_body()

    result = service.authenticate(
        webhook_endpoint_id=ENDPOINT_ID,
        signature_header=_signature(raw_body),
        raw_body=raw_body,
    )

    assert result.github_webhook_credential_id == (
        CREDENTIAL_ID
    )
    assert (
        result.github_webhook_credential_authority_id
        == AUTHORITY_ID
    )
    assert result.webhook_endpoint_id == ENDPOINT_ID
    assert result.repository_id == "123"

    assert credential_store.endpoint_ids == [
        ENDPOINT_ID
    ]
    assert secret_resolver.secret_refs == [
        "SECRET_A"
    ]
    assert authority_store.calls == [
        (
            CREDENTIAL_ID,
            "123",
        )
    ]


def test_unknown_endpoint_is_not_found():
    service = _service(
        credential_store=CredentialStore(
            error=GitHubWebhookCredentialNotFoundError(
                "missing"
            )
        )
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookEndpointNotFoundError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )


def test_credential_store_failure_propagates_as_store_error():
    service = _service(
        credential_store=CredentialStore(
            error=GitHubWebhookCredentialStoreError(
                "storage unavailable"
            )
        )
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookAuthenticationStoreError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )


def test_secret_resolution_failure_is_not_authentication_absence():
    service = _service(
        secret_resolver=SecretResolver(
            error=GitHubWebhookSecretNotFoundError(
                "missing secret"
            )
        )
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookSecretResolutionError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )


def test_invalid_signature_stops_before_body_parse_and_authority_lookup():
    authority_store = AuthorityStore()

    service = _service(
        authority_store=authority_store
    )

    with pytest.raises(
        GitHubWebhookSignatureError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header="sha256=" + "0" * 64,
            raw_body=b'{"broken":',
        )

    assert authority_store.calls == []


@pytest.mark.parametrize(
    "repository_id",
    [
        None,
        "",
        "123",
        True,
        0,
        -1,
    ],
)
def test_repository_identity_is_strict(
    repository_id,
):
    authority_store = AuthorityStore()

    service = _service(
        authority_store=authority_store
    )

    raw_body = _raw_body(repository_id)

    with pytest.raises(
        GitHubWebhookRepositoryIdentityError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )

    assert authority_store.calls == []


def test_missing_authority_fails_closed():
    service = _service(
        authority_store=AuthorityStore(
            error=StoreAuthorityNotFoundError(
                "not authorized"
            )
        )
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )


def test_authority_store_failure_is_not_not_found():
    service = _service(
        authority_store=AuthorityStore(
            error=(
                GitHubWebhookCredentialAuthorityStoreError(
                    "storage unavailable"
                )
            )
        )
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookAuthenticationStoreError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )


def test_wrong_credential_cannot_use_repository_authority():
    authority_store = AuthorityStore(
        error=StoreAuthorityNotFoundError(
            "credential not authorized"
        )
    )

    service = _service(
        authority_store=authority_store
    )

    raw_body = _raw_body()

    with pytest.raises(
        GitHubWebhookCredentialAuthorityNotFoundError
    ):
        service.authenticate(
            webhook_endpoint_id=ENDPOINT_ID,
            signature_header=_signature(raw_body),
            raw_body=raw_body,
        )

    assert authority_store.calls == [
        (
            CREDENTIAL_ID,
            "123",
        )
    ]


def test_authenticated_result_contains_no_secret_material():
    service = _service()
    raw_body = _raw_body()

    result = service.authenticate(
        webhook_endpoint_id=ENDPOINT_ID,
        signature_header=_signature(raw_body),
        raw_body=raw_body,
    )

    serialized = result.model_dump()

    assert "secret_ref" not in serialized
    assert "secret" not in serialized
