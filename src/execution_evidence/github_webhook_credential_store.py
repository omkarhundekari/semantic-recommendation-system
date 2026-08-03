from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
)


class GitHubWebhookCredentialStoreError(RuntimeError):
    pass


class GitHubWebhookCredentialNotFoundError(
    GitHubWebhookCredentialStoreError
):
    pass


class GitHubWebhookCredentialAlreadyExistsError(
    GitHubWebhookCredentialStoreError
):
    pass


class GitHubWebhookCredentialTransitionError(
    GitHubWebhookCredentialStoreError
):
    pass


class GitHubWebhookCredentialStore(ABC):
    @abstractmethod
    def create(
        self,
        credential: GitHubWebhookCredential,
    ) -> GitHubWebhookCredential:
        """Create one current webhook credential.

        New credentials must begin current. Retirement is
        structurally reserved but is not writable through
        this contract.
        """
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        github_webhook_credential_id: str,
    ) -> GitHubWebhookCredential:
        raise NotImplementedError

    @abstractmethod
    def load_current_by_webhook_endpoint_id(
        self,
        webhook_endpoint_id: str,
    ) -> GitHubWebhookCredential:
        """Load the current exact endpoint credential.

        Endpoint matching is exact. Implementations must
        never trim, normalize, case-fold, alias, or infer
        endpoint identity.
        """
        raise NotImplementedError
