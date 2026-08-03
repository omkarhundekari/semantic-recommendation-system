from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from execution_evidence.github_source_binding import (
    GitHubSourceBinding,
)


class GitHubSourceBindingStoreError(RuntimeError):
    pass


class GitHubSourceBindingNotFoundError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingAlreadyExistsError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingWorkspaceNotFoundError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingProjectNotFoundError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingProjectScopeError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingTransitionError(
    GitHubSourceBindingStoreError
):
    pass


class GitHubSourceBindingStore(ABC):
    @abstractmethod
    def create(
        self,
        binding: GitHubSourceBinding,
    ) -> GitHubSourceBinding:
        """Create one current repository binding.

        Implementations must reject bindings that already
        contain retirement metadata.

        Multiple historical bindings may exist for one
        repository, but at most one may be current.
        """
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        github_source_binding_id: str,
    ) -> GitHubSourceBinding:
        raise NotImplementedError

    @abstractmethod
    def load_current_by_repository_id(
        self,
        repository_id: str,
    ) -> GitHubSourceBinding:
        """Load the current exact repository binding.

        repository_id matching is exact. Implementations
        must not trim, coerce, normalize, or infer it from
        repository names or webhook metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def list_repository_history(
        self,
        repository_id: str,
    ) -> List[GitHubSourceBinding]:
        raise NotImplementedError

    @abstractmethod
    def list_project_bindings(
        self,
        *,
        workspace_id: str,
        project_id: str,
    ) -> List[GitHubSourceBinding]:
        raise NotImplementedError
