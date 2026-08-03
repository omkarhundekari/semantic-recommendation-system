from __future__ import annotations

from abc import ABC, abstractmethod


class GitHubWebhookSecretResolverError(RuntimeError):
    pass


class GitHubWebhookSecretNotFoundError(
    GitHubWebhookSecretResolverError
):
    pass


class GitHubWebhookSecretResolver(ABC):
    @abstractmethod
    def resolve(
        self,
        secret_ref: str,
    ) -> bytes:
        raise NotImplementedError
