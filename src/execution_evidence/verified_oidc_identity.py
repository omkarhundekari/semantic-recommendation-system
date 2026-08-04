from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class VerifiedOIDCIdentity(BaseModel):
    """Identity claims produced only after OIDC verification.

    The verifier is responsible for signature, issuer,
    audience, expiry, not-before, algorithm, and key
    validation before constructing this value.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    identity_provider_id: str = Field(
        min_length=1
    )
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)

    @field_validator("identity_provider_id")
    @classmethod
    def validate_identity_provider_id(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Verified OIDC identity provider ID "
                "must not contain surrounding whitespace."
            )

        if not value.startswith("idp_"):
            raise ValueError(
                "Verified OIDC identity provider ID "
                "must start with 'idp_'."
            )

        return value

    @field_validator(
        "issuer",
        "subject",
    )
    @classmethod
    def preserve_exact_identity(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Verified OIDC identity values must not "
                "contain surrounding whitespace."
            )

        if not value:
            raise ValueError(
                "Verified OIDC identity values must be "
                "non-empty."
            )

        return value
