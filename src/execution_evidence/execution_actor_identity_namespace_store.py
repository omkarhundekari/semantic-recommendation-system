from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from execution_evidence.execution_actor_identity_namespace import (
    ExecutionActorIdentityNamespace,
)


class ExecutionActorIdentityNamespaceStoreError(
    RuntimeError
):
    pass


class ExecutionActorIdentityNamespaceNotFoundError(
    ExecutionActorIdentityNamespaceStoreError
):
    pass


class ExecutionActorIdentityNamespaceAlreadyExistsError(
    ExecutionActorIdentityNamespaceStoreError
):
    pass


class ExecutionActorIdentityNamespaceProviderNotFoundError(
    ExecutionActorIdentityNamespaceStoreError
):
    pass


class ExecutionActorIdentityNamespaceTransitionError(
    ExecutionActorIdentityNamespaceStoreError
):
    pass


class ExecutionActorIdentityNamespaceStore(ABC):
    @abstractmethod
    def create(
        self,
        namespace: ExecutionActorIdentityNamespace,
    ) -> ExecutionActorIdentityNamespace:
        """Create one current namespace.

        Implementations must reject namespaces that
        already contain retirement metadata.
        """
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        execution_actor_namespace_id: str,
    ) -> ExecutionActorIdentityNamespace:
        raise NotImplementedError

    @abstractmethod
    def load_current_by_source_provider(
        self,
        source_provider: str,
    ) -> ExecutionActorIdentityNamespace:
        """Load the current exact provider mapping.

        source_provider matching is exact. Implementations
        must not trim, normalize, case-fold, or alias it.
        """
        raise NotImplementedError

    @abstractmethod
    def list_for_identity_provider(
        self,
        identity_provider_id: str,
    ) -> List[ExecutionActorIdentityNamespace]:
        raise NotImplementedError
