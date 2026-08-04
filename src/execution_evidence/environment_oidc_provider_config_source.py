from __future__ import annotations

import json
import os
from typing import Mapping, Optional, Tuple

from pydantic import ValidationError

from execution_evidence.oidc_provider_config import (
    OIDCProviderConfig,
)
from execution_evidence.oidc_provider_config_source import (
    OIDCProviderConfigSource,
    OIDCProviderConfigSourceError,
)


OIDC_PROVIDERS_JSON_ENV = (
    "SOLVYN_OIDC_PROVIDERS_JSON"
)

MAX_OIDC_PROVIDER_CONFIG_BYTES = 64 * 1024
MAX_OIDC_CONFIGURED_PROVIDERS = 20


class EnvironmentOIDCProviderConfigSource(
    OIDCProviderConfigSource
):
    """Load non-secret OIDC verification metadata from env.

    The configured value must contain only public
    verification metadata. Client secrets, private keys,
    refresh tokens, and other credentials do not belong in
    this configuration source.
    """

    def __init__(
        self,
        *,
        environ: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._environ = (
            environ
            if environ is not None
            else os.environ
        )

    def load(
        self,
    ) -> Tuple[OIDCProviderConfig, ...]:
        raw = self._environ.get(
            OIDC_PROVIDERS_JSON_ENV
        )

        if raw is None or not raw.strip():
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration is not "
                "configured."
            )

        if (
            len(raw.encode("utf-8"))
            > MAX_OIDC_PROVIDER_CONFIG_BYTES
        ):
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration exceeds "
                "the maximum allowed size."
            )

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration is not "
                "valid JSON."
            ) from error

        if not isinstance(payload, list):
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration must be "
                "a JSON array."
            )

        if (
            not payload
            or len(payload)
            > MAX_OIDC_CONFIGURED_PROVIDERS
        ):
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration contains "
                "an invalid provider count."
            )

        configs = []

        try:
            for item in payload:
                if not isinstance(item, dict):
                    raise OIDCProviderConfigSourceError(
                        "Each OIDC provider configuration "
                        "must be an object."
                    )

                configs.append(
                    OIDCProviderConfig(**item)
                )
        except ValidationError as error:
            raise OIDCProviderConfigSourceError(
                "OIDC provider configuration failed "
                "validation."
            ) from error

        provider_ids = [
            config.identity_provider_id
            for config in configs
        ]

        if len(set(provider_ids)) != len(provider_ids):
            raise OIDCProviderConfigSourceError(
                "OIDC identity provider IDs must be "
                "unique."
            )

        issuers = [
            config.issuer
            for config in configs
        ]

        if len(set(issuers)) != len(issuers):
            raise OIDCProviderConfigSourceError(
                "OIDC provider issuers must be unique."
            )

        return tuple(configs)
