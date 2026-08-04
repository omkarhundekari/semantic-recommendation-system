from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)


class ProjectAccessError(RuntimeError):
    pass


class ProjectAccessNotFoundError(
    ProjectAccessError
):
    """Project scope is absent or inaccessible.

    Missing workspace membership, inactive membership,
    inactive principal, missing project, and wrong tenant
    intentionally collapse to this error.
    """

    pass


class ProjectAccessStoreError(
    ProjectAccessError
):
    pass


class ProjectAccessService(ABC):
    @abstractmethod
    def authorize(
        self,
        *,
        principal: AuthenticatedRequestPrincipal,
        workspace_id: str,
        project_id: str,
    ) -> AuthorizedProjectContext:
        """Authorize tenancy access to one project.

        Active membership grants workspace tenancy access
        only. Operation-specific capabilities belong to a
        later authorization milestone.
        """
        raise NotImplementedError
