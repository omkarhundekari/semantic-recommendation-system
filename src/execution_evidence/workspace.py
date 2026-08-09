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


WorkspaceKind = Literal[
    "internal",
    "provisioned",
]


class ProvisionedWorkspace(BaseModel):
    """Self-service workspace with canonical product identity."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    workspace_id: str = Field(min_length=1)
    workspace_kind: Literal["provisioned"] = (
        "provisioned"
    )
    created_at: datetime
    updated_at: datetime

    @field_validator("workspace_id")
    @classmethod
    def validate_workspace_id(
        cls,
        value: str,
    ) -> str:
        prefix = "wsp_"

        if not value.startswith(prefix):
            raise ValueError(
                "Provisioned workspace IDs must "
                "start with 'wsp_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Provisioned workspace IDs must "
                "contain a valid UUID."
            ) from error

        if (
            parsed.version != 4
            or str(parsed) != raw_uuid
        ):
            raise ValueError(
                "Provisioned workspace IDs must "
                "contain a canonical UUID4."
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
                "Provisioned workspace timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_timestamp_order(
        self,
    ) -> "ProvisionedWorkspace":
        if self.updated_at < self.created_at:
            raise ValueError(
                "Provisioned workspace updated_at "
                "cannot precede created_at."
            )

        return self


def create_workspace_id() -> str:
    return f"wsp_{uuid4()}"
