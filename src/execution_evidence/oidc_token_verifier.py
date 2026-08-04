from __future__ import annotations

from abc import ABC, abstractmethod

from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


class OIDCTokenVerifierError(RuntimeError):
    pass


class OIDCTokenInvalidError(
    OIDCTokenVerifierError
):
    pass


class OIDCTokenVerifierUnavailableError(
    OIDCTokenVerifierError
):
    pass


class OIDCTokenVerifier(ABC):
    @abstractmethod
    def verify(
        self,
        token: str,
    ) -> VerifiedOIDCIdentity:
        """Verify one OIDC bearer token.

        Concrete implementations must fail closed and
        validate at least:

        - an explicitly allowlisted signature algorithm
        - signature against the selected trusted issuer
        - exact configured issuer
        - required audience
        - required expiration
        - not-before when present
        - non-empty subject
        - trusted JWKS key selection

        Callers must never treat token claims as verified
        before this method returns successfully.
        """
        raise NotImplementedError
