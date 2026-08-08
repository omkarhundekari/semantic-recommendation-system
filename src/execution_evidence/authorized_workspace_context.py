from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from execution_evidence.workspace_membership import (
    WorkspaceMembershipRole,
)


class AuthorizedWorkspaceContext(BaseModel):
    """Request-scoped proof of workspace tenancy access.

    This context proves only that the authenticated
    principal has an active membership in the selected
    workspace. Operation-specific permissions are enforced
    separately through workspace capabilities.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    principal_id: str = Field(min_length=1)
    membership_id: str = Field(min_length=1)
    membership_role: Optional[
        WorkspaceMembershipRole
    ] = None
    workspace_id: str = Field(min_length=1)

    @field_validator("principal_id")
    @classmethod
    def validate_principal_id(
        cls,
        value: str,
    ) -> str:
        return _validate_prefixed_uuid4(
            value,
            prefix="prn_",
            label="Principal ID",
        )

    @field_validator("membership_id")
    @classmethod
    def validate_membership_id(
        cls,
        value: str,
    ) -> str:
        return _validate_prefixed_uuid4(
            value,
            prefix="wsm_",
            label="Workspace membership ID",
        )

    @field_validator("workspace_id")
    @classmethod
    def preserve_exact_scope(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Authorized workspace scope values must "
                "not contain surrounding whitespace."
            )

        if not value:
            raise ValueError(
                "Authorized workspace scope values must "
                "be non-empty."
            )

        return value


def _validate_prefixed_uuid4(
    value: str,
    *,
    prefix: str,
    label: str,
) -> str:
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

    return value
