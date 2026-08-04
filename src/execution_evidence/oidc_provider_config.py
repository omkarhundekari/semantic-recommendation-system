from __future__ import annotations

from typing import Dict, Tuple
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class OIDCProviderConfigurationError(RuntimeError):
    pass


class OIDCProviderConfigurationNotFoundError(
    OIDCProviderConfigurationError
):
    pass


class OIDCProviderConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    identity_provider_id: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    jwks_uri: str = Field(min_length=1)
    allowed_algorithms: Tuple[str, ...] = ("RS256",)

    @field_validator(
        "identity_provider_id",
        "issuer",
        "audience",
        "jwks_uri",
    )
    @classmethod
    def require_exact_nonempty_text(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "OIDC provider configuration values "
                "must not contain surrounding whitespace."
            )

        if not value:
            raise ValueError(
                "OIDC provider configuration values "
                "must be non-empty."
            )

        return value

    @field_validator("identity_provider_id")
    @classmethod
    def require_provider_id(
        cls,
        value: str,
    ) -> str:
        if not value.startswith("idp_"):
            raise ValueError(
                "OIDC identity provider ID must start "
                "with 'idp_'."
            )

        return value

    @field_validator("jwks_uri")
    @classmethod
    def require_https_jwks_uri(
        cls,
        value: str,
    ) -> str:
        parsed = urlparse(value)

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError(
                "OIDC JWKS URI must be an HTTPS URL "
                "without credentials or fragments."
            )

        return value

    @model_validator(mode="after")
    def require_rs256_only(
        self,
    ) -> "OIDCProviderConfig":
        if self.allowed_algorithms != ("RS256",):
            raise ValueError(
                "OIDC provider configuration currently "
                "supports RS256 only."
            )

        return self


class OIDCProviderConfigRegistry:
    def __init__(
        self,
        configs: Tuple[OIDCProviderConfig, ...],
    ) -> None:
        if not configs:
            raise ValueError(
                "OIDC provider registry requires at "
                "least one provider."
            )

        by_issuer: Dict[str, OIDCProviderConfig] = {}

        for config in configs:
            if config.issuer in by_issuer:
                raise ValueError(
                    "OIDC provider issuer must be unique."
                )

            by_issuer[config.issuer] = config

        self._by_issuer = by_issuer

    def load_by_issuer(
        self,
        issuer: str,
    ) -> OIDCProviderConfig:
        config = self._by_issuer.get(issuer)

        if config is None:
            raise OIDCProviderConfigurationNotFoundError(
                "OIDC issuer is not configured."
            )

        return config
