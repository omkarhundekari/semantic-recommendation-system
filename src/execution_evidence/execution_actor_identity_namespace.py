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


class ExecutionActorIdentityNamespace(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    execution_actor_namespace_id: str = Field(
        min_length=1
    )
    source_provider: str = Field(min_length=1)
    identity_provider_id: str = Field(
        min_length=1
    )
    issuer: str = Field(min_length=1)
    created_at: datetime
    retired_at: Optional[datetime] = None
    retired_reason: Optional[str] = None

    @field_validator(
        "execution_actor_namespace_id"
    )
    @classmethod
    def validate_namespace_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="ean_",
            label="Execution actor namespace ID",
        )
        return value

    @field_validator("identity_provider_id")
    @classmethod
    def validate_identity_provider_id(
        cls,
        value: str,
    ) -> str:
        _validate_prefixed_uuid4(
            value,
            prefix="idp_",
            label="Identity provider ID",
        )
        return value

    @field_validator(
        "source_provider",
        "issuer",
    )
    @classmethod
    def preserve_exact_identity_value(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Execution actor identity namespace "
                "values must not contain surrounding "
                "whitespace."
            )

        if not value:
            raise ValueError(
                "Execution actor identity namespace "
                "values must be non-empty."
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
                "Execution actor identity namespace "
                "timestamps must be timezone-aware."
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
    ) -> "ExecutionActorIdentityNamespace":
        if self.retired_at is None:
            if self.retired_reason is not None:
                raise ValueError(
                    "Current execution actor identity "
                    "namespaces cannot contain a "
                    "retirement reason."
                )

            return self

        if self.retired_reason is None:
            raise ValueError(
                "Retired execution actor identity "
                "namespaces require a retirement "
                "reason."
            )

        if self.retired_at < self.created_at:
            raise ValueError(
                "Execution actor identity namespace "
                "retired_at cannot precede "
                "created_at."
            )

        return self


def create_execution_actor_namespace_id() -> str:
    return f"ean_{uuid4()}"


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
