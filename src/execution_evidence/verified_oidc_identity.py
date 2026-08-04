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

    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)

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
