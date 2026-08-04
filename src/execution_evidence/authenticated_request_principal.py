from __future__ import annotations

from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class AuthenticatedRequestPrincipal(BaseModel):
    """Durable principal authenticated for one request.

    This identifies the calling principal. It is distinct
    from an execution-event actor and from authorization
    to any workspace or project.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    principal_id: str = Field(min_length=1)
    identity_provider_id: str = Field(min_length=1)
    identity_link_id: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)

    @field_validator("principal_id")
    @classmethod
    def validate_principal_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="prn_",
            label="Principal ID",
        )
        return value

    @field_validator("identity_provider_id")
    @classmethod
    def validate_provider_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="idp_",
            label="Identity provider ID",
        )
        return value

    @field_validator("identity_link_id")
    @classmethod
    def validate_link_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="pil_",
            label="Principal identity link ID",
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
                "Authenticated request identity values "
                "must not contain surrounding whitespace."
            )

        if not value:
            raise ValueError(
                "Authenticated request identity values "
                "must be non-empty."
            )

        return value


def _validate_prefixed_uuid4(
    value: str,
    *,
    prefix: str,
    label: str,
) -> None:
    if value != value.strip():
        raise ValueError(
            f"{label} must not contain surrounding "
            "whitespace."
        )

    if not value.startswith(prefix):
        raise ValueError(
            f"{label} must start with {prefix!r}."
        )

    raw_uuid = value[len(prefix):]

    try:
        parsed = UUID(raw_uuid)
    except ValueError as error:
        raise ValueError(
            f"{label} must contain a valid UUID."
        ) from error

    if (
        parsed.version != 4
        or str(parsed) != raw_uuid
    ):
        raise ValueError(
            f"{label} must contain a canonical UUID4."
        )
