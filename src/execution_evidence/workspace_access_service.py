from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)


class WorkspaceAccessError(RuntimeError):
    pass


class WorkspaceAccessNotFoundError(
    WorkspaceAccessError
):
    """Workspace scope is absent or inaccessible.

    Missing workspace membership, inactive membership,
    inactive principal, and nonexistent workspace
    intentionally collapse to this error.
    """

    pass


class WorkspaceAccessStoreError(
    WorkspaceAccessError
):
    pass


class WorkspaceAccessService(ABC):
    @abstractmethod
    def authorize(
        self,
        *,
        principal: AuthenticatedRequestPrincipal,
        workspace_id: str,
    ) -> AuthorizedWorkspaceContext:
        """Authorize tenancy access to one workspace.

        Active membership grants workspace tenancy access
        only. Operation-specific permissions are enforced
        separately through workspace capabilities.
        """
        raise NotImplementedError
