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


class GitHubSourceBinding(BaseModel):
    """Trusted binding from a GitHub repository to Solvyn scope.

    repository_id is the exact GitHub repository identity.
    It must never be inferred from repository names, owners,
    webhook URLs, or other mutable payload metadata.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    github_source_binding_id: str = Field(
        min_length=1
    )
    repository_id: str = Field(min_length=1)
    installation_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    workspace_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    created_at: datetime
    retired_at: Optional[datetime] = None
    retired_reason: Optional[str] = None

    @field_validator("github_source_binding_id")
    @classmethod
    def validate_binding_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="gsb_",
            label="GitHub source binding ID",
        )
        return value

    @field_validator(
        "repository_id",
        "installation_id",
        "workspace_id",
        "project_id",
    )
    @classmethod
    def preserve_exact_identity_values(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        if not value:
            raise ValueError(
                "GitHub source binding identity "
                "values must be non-empty."
            )

        if value != value.strip():
            raise ValueError(
                "GitHub source binding identity "
                "values must not contain surrounding "
                "whitespace."
            )

        return value

    @field_validator("repository_id")
    @classmethod
    def require_numeric_repository_id(
        cls,
        value: str,
    ) -> str:
        if not value.isascii() or not value.isdigit():
            raise ValueError(
                "GitHub repository ID must contain "
                "ASCII decimal digits only."
            )

        if value.startswith("0") and value != "0":
            raise ValueError(
                "GitHub repository ID must use its "
                "canonical decimal representation."
            )

        if int(value) < 1:
            raise ValueError(
                "GitHub repository ID must be positive."
            )

        return value

    @field_validator("installation_id")
    @classmethod
    def require_numeric_installation_id(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        if not value.isascii() or not value.isdigit():
            raise ValueError(
                "GitHub installation ID must contain "
                "ASCII decimal digits only."
            )

        if value.startswith("0") and value != "0":
            raise ValueError(
                "GitHub installation ID must use its "
                "canonical decimal representation."
            )

        if int(value) < 1:
            raise ValueError(
                "GitHub installation ID must be positive."
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
                "GitHub source binding timestamps "
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
    ) -> "GitHubSourceBinding":
        if self.retired_at is None:
            if self.retired_reason is not None:
                raise ValueError(
                    "Current GitHub source bindings "
                    "cannot contain a retirement reason."
                )

            return self

        if self.retired_reason is None:
            raise ValueError(
                "Retired GitHub source bindings require "
                "a retirement reason."
            )

        if self.retired_at < self.created_at:
            raise ValueError(
                "GitHub source binding retired_at "
                "cannot precede created_at."
            )

        return self


def create_github_source_binding_id() -> str:
    return f"gsb_{uuid4()}"


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
