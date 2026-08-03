from __future__ import annotations

from execution_evidence.github_source_binding_store import (
    GitHubSourceBindingNotFoundError,
    GitHubSourceBindingStore,
    GitHubSourceBindingStoreError,
)
from execution_evidence.github_source_routing import (
    GitHubSourceRoute,
)
from execution_evidence.github_webhook_authenticated_source import (
    GitHubWebhookAuthenticatedSource,
)


class GitHubSourceRoutingError(RuntimeError):
    pass


class GitHubSourceRoutingNotFoundError(
    GitHubSourceRoutingError
):
    pass


class GitHubSourceRoutingStoreError(
    GitHubSourceRoutingError
):
    pass


class GitHubSourceRoutingService:
    def __init__(
        self,
        *,
        binding_store: GitHubSourceBindingStore,
    ) -> None:
        self._binding_store = binding_store

    def resolve_authenticated_source(
        self,
        source: GitHubWebhookAuthenticatedSource,
    ) -> GitHubSourceRoute:
        if not isinstance(
            source,
            GitHubWebhookAuthenticatedSource,
        ):
            raise TypeError(
                "GitHub source routing requires an "
                "authenticated webhook source."
            )

        return self.resolve(source.repository_id)

    def resolve(
        self,
        repository_id: str,
    ) -> GitHubSourceRoute:
        if not isinstance(repository_id, str):
            raise ValueError(
                "GitHub repository ID must be text."
            )

        if not repository_id:
            raise ValueError(
                "GitHub repository ID must not be empty."
            )

        try:
            binding = (
                self._binding_store
                .load_current_by_repository_id(
                    repository_id
                )
            )
        except GitHubSourceBindingNotFoundError as error:
            raise GitHubSourceRoutingNotFoundError(
                "GitHub repository has no current "
                "trusted source binding."
            ) from error
        except GitHubSourceBindingStoreError as error:
            raise GitHubSourceRoutingStoreError(
                "Could not resolve trusted GitHub "
                "source routing."
            ) from error

        if binding.retired_at is not None:
            raise GitHubSourceRoutingNotFoundError(
                "GitHub repository has no current "
                "trusted source binding."
            )

        return GitHubSourceRoute(
            github_source_binding_id=(
                binding.github_source_binding_id
            ),
            repository_id=binding.repository_id,
            workspace_id=binding.workspace_id,
            project_id=binding.project_id,
        )
