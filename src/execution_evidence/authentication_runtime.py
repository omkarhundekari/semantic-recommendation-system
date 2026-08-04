from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Optional, Tuple

from execution_evidence.oidc_jwks import (
    CachedOIDCJWKSProvider,
    RequestsOIDCJWKSFetcher,
)
from execution_evidence.oidc_provider_config import (
    OIDCProviderConfigRegistry,
)
from execution_evidence.oidc_provider_config_source import (
    OIDCProviderConfigSource,
    OIDCProviderConfigSourceError,
)
from execution_evidence.pyjwt_oidc_token_verifier import (
    PyJWTOIDCTokenVerifier,
)
from execution_evidence.request_authenticator import (
    RequestAuthenticator,
)
from execution_evidence.sqlite_request_principal_resolver import (
    SQLiteRequestPrincipalResolver,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
)


logger = logging.getLogger(__name__)


AuthenticationRuntimeStatus = Literal[
    "ready",
    "misconfigured",
    "unavailable_storage",
]


@dataclass(frozen=True)
class AuthenticationRuntime:
    status: AuthenticationRuntimeStatus
    authenticator: Optional[RequestAuthenticator]
    configured_provider_ids: Tuple[str, ...]
    errors: Tuple[str, ...]

    @property
    def ready(self) -> bool:
        return (
            self.status == "ready"
            and self.authenticator is not None
        )


def build_authentication_runtime(
    *,
    config_source: OIDCProviderConfigSource,
    trusted_sqlite_service: Optional[
        TrustedSQLiteStorageService
    ],
) -> AuthenticationRuntime:
    try:
        configs = config_source.load()
        registry = OIDCProviderConfigRegistry(
            configs
        )
    except (
        OIDCProviderConfigSourceError,
        ValueError,
    ) as error:
        logger.error(
            "Interactive OIDC authentication runtime is "
            "misconfigured: %s",
            error,
        )

        return AuthenticationRuntime(
            status="misconfigured",
            authenticator=None,
            configured_provider_ids=(),
            errors=(
                "Interactive OIDC authentication is "
                "misconfigured.",
            ),
        )

    provider_ids = tuple(
        config.identity_provider_id
        for config in configs
    )

    logger.info(
        "Configured interactive OIDC identity providers: %s",
        ", ".join(provider_ids),
    )

    if trusted_sqlite_service is None:
        logger.error(
            "Interactive OIDC authentication runtime "
            "cannot resolve durable principals because "
            "trusted SQLite storage is unavailable. "
            "Configured providers: %s",
            ", ".join(provider_ids),
        )

        return AuthenticationRuntime(
            status="unavailable_storage",
            authenticator=None,
            configured_provider_ids=provider_ids,
            errors=(
                "Durable principal resolution storage "
                "is unavailable.",
            ),
        )

    # These objects are intentionally process-shared.
    # JWKS cache TTL, unknown-kid throttling, and
    # single-flight refresh all depend on shared state.
    jwks_provider = CachedOIDCJWKSProvider(
        fetcher=RequestsOIDCJWKSFetcher()
    )

    verifier = PyJWTOIDCTokenVerifier(
        provider_registry=registry,
        jwks_provider=jwks_provider,
    )

    resolver = SQLiteRequestPrincipalResolver(
        trusted_sqlite_service.path
    )

    authenticator = RequestAuthenticator(
        token_verifier=verifier,
        principal_resolver=resolver,
    )

    logger.info(
        "Interactive OIDC authentication runtime ready "
        "for providers: %s",
        ", ".join(provider_ids),
    )

    return AuthenticationRuntime(
        status="ready",
        authenticator=authenticator,
        configured_provider_ids=provider_ids,
        errors=(),
    )
