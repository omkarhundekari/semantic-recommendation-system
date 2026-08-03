from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipMutationResult,
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
    def transition_status(
        self,
        membership_id: str,
        *,
        new_status: WorkspaceMembershipStatus,
        changed_at: datetime,
        expected_revision: int,
        reason: Optional[str] = None,
    ) -> WorkspaceMembershipMutationResult:
        raise NotImplementedError

    @abstractmethod
    def list_transitions(
        self,
        membership_id: str,
    ) -> List[WorkspaceMembershipTransition]:
        raise NotImplementedError
