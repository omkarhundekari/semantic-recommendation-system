from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


class RequestPrincipalResolutionError(RuntimeError):
    pass


class RequestPrincipalNotFoundError(
    RequestPrincipalResolutionError
):
    pass


class RequestPrincipalResolutionStoreError(
    RequestPrincipalResolutionError
):
    pass


class RequestPrincipalResolver(ABC):
    @abstractmethod
    def resolve(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> AuthenticatedRequestPrincipal:
        """Resolve verified external identity to a principal.

        Unknown identities, disabled providers, ended
        links, and inactive principals must fail closed.
        """
        raise NotImplementedError
