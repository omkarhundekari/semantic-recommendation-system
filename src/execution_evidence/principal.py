from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


PrincipalStatus = Literal[
    "active",
    "suspended",
    "deactivated",
]


class Principal(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    principal_id: str = Field(min_length=1)
    principal_kind: str = Field(min_length=1)
    status: PrincipalStatus = "active"
    created_at: datetime
    updated_at: datetime

    @field_validator("principal_id")
    @classmethod
    def validate_principal_id(
        cls,
        value: str,
    ) -> str:
        prefix = "prn_"

        if not value.startswith(prefix):
            raise ValueError(
                "Principal IDs must start with 'prn_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Principal IDs must contain a valid "
                "UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Principal IDs must contain a "
                "canonical UUID4."
            )

        return value

    @field_validator(
        "principal_kind",
    )
    @classmethod
    def normalize_principal_kind(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "Principal kind must be non-empty."
            )

        return normalized

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
                "Principal timestamps must be "
                "timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def require_monotonic_timestamps(
        self,
    ) -> "Principal":
        if self.updated_at < self.created_at:
            raise ValueError(
                "Principal updated_at cannot precede "
                "created_at."
            )

        return self


def create_principal_id() -> str:
    return f"prn_{uuid4()}"
