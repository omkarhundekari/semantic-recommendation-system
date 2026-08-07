from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipMutationResult,
    WorkspaceMembershipRole,
    WorkspaceMembershipRoleMutationResult,
    WorkspaceMembershipRoleTransition,
    WorkspaceMembershipStatus,
    WorkspaceMembershipTransition,
)


class WorkspaceMembershipStoreError(
    RuntimeError
):
    pass


class WorkspaceMembershipNotFoundError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipAlreadyExistsError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipInactiveError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipRevisionConflictError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipTransitionError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipRoleAuthorizationError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipLastManagerError(
    WorkspaceMembershipTransitionError
):
    pass


class WorkspaceNotFoundError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipPrincipalNotFoundError(
    WorkspaceMembershipStoreError
):
    pass


class WorkspaceMembershipStore(ABC):
    @property
    @abstractmethod
    def workspace_id(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        raise NotImplementedError

    @abstractmethod
    def load_by_id(
        self,
        membership_id: str,
    ) -> WorkspaceMembership:
        raise NotImplementedError

    @abstractmethod
    def load_current(
        self,
        principal_id: str,
    ) -> WorkspaceMembership:
        raise NotImplementedError

    @abstractmethod
    def require_active(
        self,
        principal_id: str,
    ) -> WorkspaceMembership:
        raise NotImplementedError

    @abstractmethod
    def list_current_memberships(
        self,
    ) -> List[WorkspaceMembership]:
        raise NotImplementedError

    @abstractmethod
    def transition_role(
        self,
        membership_id: str,
        *,
        new_role: WorkspaceMembershipRole,
        changed_at: datetime,
        expected_revision: int,
        changed_by_principal_id: str,
        reason: Optional[str] = None,
    ) -> WorkspaceMembershipRoleMutationResult:
        raise NotImplementedError

    @abstractmethod
    def list_role_transitions(
        self,
        membership_id: str,
    ) -> List[WorkspaceMembershipRoleTransition]:
        raise NotImplementedError

    @abstractmethod
    def transition_status(
        self,
        membership_id: str,
        *,
        new_status: WorkspaceMembershipStatus,
        changed_at: datetime,
        expected_revision: int,
        reason: Optional[str] = None,
        changed_by_principal_id: Optional[str] = None,
    ) -> WorkspaceMembershipMutationResult:
        raise NotImplementedError

    @abstractmethod
    def list_transitions(
        self,
        membership_id: str,
    ) -> List[WorkspaceMembershipTransition]:
        raise NotImplementedError
