from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class GitHubWebhookCredentialAuthority(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    github_webhook_credential_authority_id: str = Field(
        min_length=1
    )
    github_webhook_credential_id: str = Field(
        min_length=1
    )
    repository_id: str = Field(min_length=1)
    created_at: datetime
    retired_at: Optional[datetime] = None
    retired_reason: Optional[str] = None

    @field_validator(
        "github_webhook_credential_authority_id"
    )
    @classmethod
    def validate_authority_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="gwa_",
            label="GitHub webhook credential authority ID",
        )
        return value

    @field_validator(
        "github_webhook_credential_id"
    )
    @classmethod
    def validate_credential_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="gwc_",
            label="GitHub webhook credential ID",
        )
        return value

    @field_validator("repository_id")
    @classmethod
    def validate_repository_id(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "GitHub webhook authority repository "
                "ID must not contain surrounding whitespace."
            )

        if not value.isascii() or not value.isdigit():
            raise ValueError(
                "GitHub webhook authority repository "
                "ID must contain ASCII decimal digits only."
            )

        if value.startswith("0") and value != "0":
            raise ValueError(
                "GitHub webhook authority repository "
                "ID must use its canonical decimal "
                "representation."
            )

        if int(value) < 1:
            raise ValueError(
                "GitHub webhook authority repository "
                "ID must be positive."
            )

        return value

    @field_validator(
        "created_at",
        "retired_at",
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
                "GitHub webhook authority timestamps "
                "must be timezone-aware."
            )

        return value

    @field_validator("retired_reason")
    @classmethod
    def normalize_retired_reason(
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
    ) -> "GitHubWebhookCredentialAuthority":
        if self.retired_at is None:
            if self.retired_reason is not None:
                raise ValueError(
                    "Current GitHub webhook authorities "
                    "cannot contain a retirement reason."
                )

            return self

        if self.retired_reason is None:
            raise ValueError(
                "Retired GitHub webhook authorities "
                "require a retirement reason."
            )

        if self.retired_at < self.created_at:
            raise ValueError(
                "GitHub webhook authority retired_at "
                "cannot precede created_at."
            )

        return self


def create_github_webhook_credential_authority_id() -> str:
    return f"gwa_{uuid4()}"


def _validate_prefixed_uuid4(
    value: str,
    *,
    prefix: str,
    label: str,
) -> None:
    if not value.startswith(prefix):
        raise ValueError(
            f"{label}s must start with {prefix!r}."
        )

    raw_uuid = value[len(prefix):]

    try:
        parsed_uuid = UUID(raw_uuid)
    except ValueError as error:
        raise ValueError(
            f"{label}s must contain a valid UUID."
        ) from error

    if (
        parsed_uuid.version != 4
        or str(parsed_uuid) != raw_uuid
    ):
        raise ValueError(
            f"{label}s must contain a canonical UUID4."
        )
