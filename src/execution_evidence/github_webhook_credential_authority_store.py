from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from execution_evidence.github_webhook_credential_authority import (
    GitHubWebhookCredentialAuthority,
)


class GitHubWebhookCredentialAuthorityStoreError(
    RuntimeError
):
    pass


class GitHubWebhookCredentialAuthorityNotFoundError(
    GitHubWebhookCredentialAuthorityStoreError
):
    pass


class GitHubWebhookCredentialAuthorityAlreadyExistsError(
    GitHubWebhookCredentialAuthorityStoreError
):
    pass


class GitHubWebhookCredentialAuthorityCredentialNotFoundError(
    GitHubWebhookCredentialAuthorityStoreError
):
    pass


class GitHubWebhookCredentialAuthorityTransitionError(
    GitHubWebhookCredentialAuthorityStoreError
):
    pass


class GitHubWebhookCredentialAuthorityStore(ABC):
    @abstractmethod
    def create(
        self,
        authority: GitHubWebhookCredentialAuthority,
    ) -> GitHubWebhookCredentialAuthority:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        github_webhook_credential_authority_id: str,
    ) -> GitHubWebhookCredentialAuthority:
        raise NotImplementedError

    @abstractmethod
    def load_current(
        self,
        *,
        github_webhook_credential_id: str,
        repository_id: str,
    ) -> GitHubWebhookCredentialAuthority:
        raise NotImplementedError

    @abstractmethod
    def list_for_credential(
        self,
        github_webhook_credential_id: str,
    ) -> List[GitHubWebhookCredentialAuthority]:
        raise NotImplementedError
