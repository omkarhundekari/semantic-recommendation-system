from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def _validate_prefixed_uuid4(
    value: str,
    *,
    prefix: str,
    label: str,
) -> str:
    if not value.startswith(prefix):
        raise ValueError(
            f"{label} must start with '{prefix}'."
        )

    raw_uuid = value[len(prefix):]

    try:
        parsed_uuid = UUID(raw_uuid)
    except ValueError as error:
        raise ValueError(
            f"{label} must contain a valid UUID."
        ) from error

    if (
        parsed_uuid.version != 4
        or str(parsed_uuid) != raw_uuid
    ):
        raise ValueError(
            f"{label} must contain a canonical UUID4."
        )

    return value


IdentityProviderKind = Literal[
    "google",
    "github",
    "microsoft",
    "oidc",
    "saml",
]

IdentityProviderStatus = Literal[
    "active",
    "disabled",
]

PrincipalIdentityLinkStatus = Literal[
    "active",
    "ended",
]


class IdentityProvider(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    identity_provider_id: str = Field(
        min_length=1
    )
    provider_kind: IdentityProviderKind
    issuer: str = Field(min_length=1)
    status: IdentityProviderStatus = "active"
    created_at: datetime
    updated_at: datetime

    @field_validator("identity_provider_id")
    @classmethod
    def validate_identity_provider_id(
        cls,
        value: str,
    ) -> str:
        return _validate_prefixed_uuid4(
            value,
            prefix="idp_",
            label="Identity provider IDs",
        )

    @field_validator("issuer")
    @classmethod
    def validate_issuer(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Identity provider issuer must not "
                "contain surrounding whitespace."
            )

        if not value:
            raise ValueError(
                "Identity provider issuer must be "
                "non-empty."
            )

        return value

    @field_validator(
        "created_at",
        "updated_at",
    )
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Identity provider timestamps must "
                "be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def require_monotonic_timestamps(
        self,
    ) -> "IdentityProvider":
        if self.updated_at < self.created_at:
            raise ValueError(
                "Identity provider updated_at cannot "
                "precede created_at."
            )

        return self


class PrincipalIdentityLink(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    link_id: str = Field(min_length=1)
    identity_provider_id: str = Field(
        min_length=1
    )
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    status: PrincipalIdentityLinkStatus
    linked_at: datetime
    ended_at: Optional[datetime] = None
    end_reason: Optional[str] = None
    ended_by_principal_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )

    @field_validator("link_id")
    @classmethod
    def validate_link_id(
        cls,
        value: str,
    ) -> str:
        prefix = "pil_"

        if not value.startswith(prefix):
            raise ValueError(
                "Principal identity link IDs must "
                "start with 'pil_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Principal identity link IDs must "
                "contain a valid UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Principal identity link IDs must "
                "contain a canonical UUID4."
            )

        return value

    @field_validator("identity_provider_id")
    @classmethod
    def validate_identity_provider_id(
        cls,
        value: str,
    ) -> str:
        return _validate_prefixed_uuid4(
            value,
            prefix="idp_",
            label="Identity provider IDs",
        )

    @field_validator(
        "issuer",
        "subject",
    )
    @classmethod
    def reject_identity_whitespace(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Principal identity values must not "
                "contain surrounding whitespace."
            )

        return value

    @field_validator(
        "principal_id",
        "ended_by_principal_id",
    )
    @classmethod
    def validate_principal_id(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        if value != value.strip():
            raise ValueError(
                "Principal identity values must not "
                "contain surrounding whitespace."
            )

        return _validate_prefixed_uuid4(
            value,
            prefix="prn_",
            label="Principal IDs",
        )

    @field_validator(
        "linked_at",
        "ended_at",
    )
    @classmethod
    def require_timezone(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Principal identity link timestamps "
                "must be timezone-aware."
            )

        return value

    @field_validator("end_reason")
    @classmethod
    def normalize_end_reason(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_lifecycle(
        self,
    ) -> "PrincipalIdentityLink":
        if self.status == "active":
            if (
                self.ended_at is not None
                or self.end_reason is not None
                or self.ended_by_principal_id
                is not None
            ):
                raise ValueError(
                    "Active principal identity links "
                    "cannot contain termination "
                    "metadata."
                )

            return self

        if self.ended_at is None:
            raise ValueError(
                "Ended principal identity links "
                "require ended_at."
            )

        if self.end_reason is None:
            raise ValueError(
                "Ended principal identity links "
                "require an end reason."
            )

        if self.ended_at < self.linked_at:
            raise ValueError(
                "Principal identity link ended_at "
                "cannot precede linked_at."
            )

        return self


def create_identity_provider_id() -> str:
    return f"idp_{uuid4()}"


def create_principal_identity_link_id() -> str:
    return f"pil_{uuid4()}"
