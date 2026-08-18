from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from execution_evidence.principal_identity import (
    IdentityProvider,
)
from execution_evidence.principal_identity_store import (
    IdentityProviderAlreadyExistsError,
    IdentityProviderNotFoundError,
    PrincipalIdentityStoreError,
)
from execution_evidence.sqlite_principal_identity_store import (
    SQLitePrincipalIdentityStore,
)


class IdentityProviderBootstrapError(RuntimeError):
    """Base error for operator identity-provider bootstrap."""


class IdentityProviderBootstrapConflictError(
    IdentityProviderBootstrapError
):
    """The requested provider conflicts with durable state."""


class IdentityProviderBootstrapStoreError(
    IdentityProviderBootstrapError
):
    """Durable identity-provider storage is unavailable."""


@dataclass(frozen=True)
class IdentityProviderBootstrapResult:
    provider: IdentityProvider
    created: bool


class IdentityProviderBootstrapService:
    """Operator-only bootstrap for durable identity providers.

    This service deliberately does not initialize storage, create
    principals, link identities, reactivate disabled providers, or
    mutate existing provider identity.

    Authentication configuration and durable provider registration
    are separate operator-controlled concerns. Both must agree on the
    same identity_provider_id and issuer before login can succeed.
    """

    def __init__(
        self,
        database_path: Path | str,
    ) -> None:
        self._database_path = Path(database_path)

    def ensure_google_provider(
        self,
        *,
        identity_provider_id: str,
        issuer: str,
        created_at: datetime,
    ) -> IdentityProviderBootstrapResult:
        desired = IdentityProvider(
            identity_provider_id=identity_provider_id,
            provider_kind="google",
            issuer=issuer,
            status="active",
            created_at=created_at,
            updated_at=created_at,
        )

        store = SQLitePrincipalIdentityStore(
            self._database_path
        )

        try:
            created = store.create_provider(desired)
        except IdentityProviderAlreadyExistsError as error:
            return self._resolve_existing_provider(
                store=store,
                desired=desired,
                create_error=error,
            )
        except PrincipalIdentityStoreError as error:
            raise IdentityProviderBootstrapStoreError(
                "Identity provider bootstrap storage "
                "is unavailable."
            ) from error

        return IdentityProviderBootstrapResult(
            provider=created,
            created=True,
        )

    @staticmethod
    def _resolve_existing_provider(
        *,
        store: SQLitePrincipalIdentityStore,
        desired: IdentityProvider,
        create_error: IdentityProviderAlreadyExistsError,
    ) -> IdentityProviderBootstrapResult:
        try:
            existing = store.load_provider(
                desired.identity_provider_id
            )
        except IdentityProviderNotFoundError as error:
            # The most important case here is issuer ownership:
            # create_provider can fail because the issuer already
            # belongs to a different provider ID. We intentionally
            # do not attempt to adopt or rewrite that provider.
            raise IdentityProviderBootstrapConflictError(
                "The requested identity provider conflicts "
                "with existing durable provider state."
            ) from create_error
        except PrincipalIdentityStoreError as error:
            raise IdentityProviderBootstrapStoreError(
                "Identity provider bootstrap storage "
                "is unavailable."
            ) from error

        if (
            existing.identity_provider_id
            != desired.identity_provider_id
            or existing.provider_kind
            != desired.provider_kind
            or existing.issuer
            != desired.issuer
        ):
            raise IdentityProviderBootstrapConflictError(
                "The requested identity provider conflicts "
                "with existing durable provider state."
            ) from create_error

        if existing.status != "active":
            # Bootstrap must never silently undo an operator disable.
            raise IdentityProviderBootstrapConflictError(
                "The existing identity provider is not active. "
                "Bootstrap will not reactivate it."
            ) from create_error

        return IdentityProviderBootstrapResult(
            provider=existing,
            created=False,
        )
