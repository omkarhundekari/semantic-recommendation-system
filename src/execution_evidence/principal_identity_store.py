from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from execution_evidence.principal_identity import (
    IdentityProvider,
    PrincipalIdentityLink,
)


class PrincipalIdentityStoreError(RuntimeError):
    pass


class IdentityProviderNotFoundError(
    PrincipalIdentityStoreError
):
    pass


class IdentityProviderAlreadyExistsError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityLinkNotFoundError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityAlreadyLinkedError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityOwnershipConflictError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityPrincipalNotFoundError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityLinkTransitionError(
    PrincipalIdentityStoreError
):
    pass


class PrincipalIdentityStore(ABC):
    @abstractmethod
    def create_provider(
        self,
        provider: IdentityProvider,
    ) -> IdentityProvider:
        raise NotImplementedError

    @abstractmethod
    def load_provider(
        self,
        identity_provider_id: str,
    ) -> IdentityProvider:
        raise NotImplementedError

    @abstractmethod
    def create_link(
        self,
        link: PrincipalIdentityLink,
    ) -> PrincipalIdentityLink:
        raise NotImplementedError

    @abstractmethod
    def load_link(
        self,
        link_id: str,
    ) -> PrincipalIdentityLink:
        raise NotImplementedError

    @abstractmethod
    def load_active_link(
        self,
        *,
        issuer: str,
        subject: str,
    ) -> PrincipalIdentityLink:
        raise NotImplementedError

    @abstractmethod
    def list_principal_links(
        self,
        principal_id: str,
    ) -> List[PrincipalIdentityLink]:
        raise NotImplementedError

    @abstractmethod
    def end_link(
        self,
        link_id: str,
        *,
        ended_at: datetime,
        end_reason: str,
        ended_by_principal_id: Optional[str] = None,
    ) -> PrincipalIdentityLink:
        raise NotImplementedError
