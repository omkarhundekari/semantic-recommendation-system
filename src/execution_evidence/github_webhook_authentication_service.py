from __future__ import annotations

import json
from typing import Optional

from execution_evidence.github_webhook_authenticated_source import (
    GitHubWebhookAuthenticatedSource,
)
from execution_evidence.github_webhook_credential_authority_store import (
    GitHubWebhookCredentialAuthorityNotFoundError as StoreCredentialAuthorityNotFoundError,
    GitHubWebhookCredentialAuthorityStore,
    GitHubWebhookCredentialAuthorityStoreError,
)
from execution_evidence.github_webhook_credential_store import (
    GitHubWebhookCredentialNotFoundError,
    GitHubWebhookCredentialStore,
    GitHubWebhookCredentialStoreError,
)
from execution_evidence.github_webhook_secret_resolver import (
    GitHubWebhookSecretResolver,
    GitHubWebhookSecretResolverError,
)
from execution_evidence.github_webhook_signature import (
    verify_github_webhook_signature,
)


class GitHubWebhookAuthenticationError(RuntimeError):
    pass


class GitHubWebhookEndpointNotFoundError(
    GitHubWebhookAuthenticationError
):
    pass


class GitHubWebhookRepositoryIdentityError(
    GitHubWebhookAuthenticationError
):
    pass


class GitHubWebhookCredentialAuthorityNotFoundError(
    GitHubWebhookAuthenticationError
):
    pass


class GitHubWebhookAuthenticationStoreError(
    GitHubWebhookAuthenticationError
):
    pass


class GitHubWebhookSecretResolutionError(
    GitHubWebhookAuthenticationError
):
    pass


class GitHubWebhookAuthenticationService:
    def __init__(
        self,
        *,
        credential_store: GitHubWebhookCredentialStore,
        authority_store: (
            GitHubWebhookCredentialAuthorityStore
        ),
        secret_resolver: GitHubWebhookSecretResolver,
    ) -> None:
        self._credential_store = credential_store
        self._authority_store = authority_store
        self._secret_resolver = secret_resolver

    def authenticate(
        self,
        *,
        webhook_endpoint_id: str,
        signature_header: Optional[str],
        raw_body: bytes,
    ) -> GitHubWebhookAuthenticatedSource:
        try:
            credential = (
                self._credential_store
                .load_current_by_webhook_endpoint_id(
                    webhook_endpoint_id
                )
            )
        except GitHubWebhookCredentialNotFoundError as error:
            raise GitHubWebhookEndpointNotFoundError(
                "GitHub webhook endpoint does not exist."
            ) from error
        except GitHubWebhookCredentialStoreError as error:
            raise GitHubWebhookAuthenticationStoreError(
                "Could not load GitHub webhook credential."
            ) from error

        try:
            secret = self._secret_resolver.resolve(
                credential.secret_ref
            )
        except GitHubWebhookSecretResolverError as error:
            raise GitHubWebhookSecretResolutionError(
                "GitHub webhook secret could not "
                "be resolved."
            ) from error

        verify_github_webhook_signature(
            secret=secret,
            raw_body=raw_body,
            signature_header=signature_header,
        )

        repository_id = self._extract_repository_id(
            raw_body
        )

        try:
            authority = (
                self._authority_store.load_current(
                    github_webhook_credential_id=(
                        credential
                        .github_webhook_credential_id
                    ),
                    repository_id=repository_id,
                )
            )
        except (
            StoreCredentialAuthorityNotFoundError
        ) as error:
            raise (
                GitHubWebhookCredentialAuthorityNotFoundError(
                    "GitHub webhook source is not "
                    "authorized."
                )
            ) from error
        except (
            GitHubWebhookCredentialAuthorityStoreError
        ) as error:
            raise GitHubWebhookAuthenticationStoreError(
                "Could not load GitHub webhook "
                "credential authority."
            ) from error

        return GitHubWebhookAuthenticatedSource(
            github_webhook_credential_id=(
                credential.github_webhook_credential_id
            ),
            github_webhook_credential_authority_id=(
                authority
                .github_webhook_credential_authority_id
            ),
            webhook_endpoint_id=(
                credential.webhook_endpoint_id
            ),
            repository_id=repository_id,
        )

    @staticmethod
    def _extract_repository_id(
        raw_body: bytes,
    ) -> str:
        try:
            payload = json.loads(raw_body)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as error:
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook body must contain "
                "valid UTF-8 JSON."
            ) from error

        if not isinstance(payload, dict):
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook JSON payload must "
                "be an object."
            )

        repository = payload.get("repository")

        if not isinstance(repository, dict):
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook repository must be "
                "an object."
            )

        repository_id = repository.get("id")

        if (
            not isinstance(repository_id, int)
            or isinstance(repository_id, bool)
            or repository_id < 1
        ):
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook repository ID must "
                "be a positive integer."
            )

        return str(repository_id)
