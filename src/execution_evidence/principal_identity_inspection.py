from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)


PrincipalIdentityInspectionKind = Literal[
    "active",
    "unknown_identity",
    "link_ended",
    "principal_suspended",
    "principal_deactivated",
    "provider_disabled",
    "provider_not_configured",
]


@dataclass(frozen=True)
class PrincipalIdentityInspection:
    """Login-path view of one verified external identity.

    This richer state MUST NOT replace the normal
    RequestPrincipalResolver.resolve() contract.

    The normal resource-server path needs only:
        resolvable -> authenticated principal
        otherwise  -> uniform authentication failure

    The login callback needs richer state so it can
    provision safely without resurrecting suspended,
    ended, disabled, or otherwise blocked identities.
    """

    kind: PrincipalIdentityInspectionKind

    principal: Optional[
        AuthenticatedRequestPrincipal
    ] = None

    principal_id: Optional[str] = None
    identity_link_id: Optional[str] = None

    def require_active(
        self,
    ) -> AuthenticatedRequestPrincipal:
        if (
            self.kind != "active"
            or self.principal is None
        ):
            raise RuntimeError(
                "Identity inspection is not active."
            )

        return self.principal
