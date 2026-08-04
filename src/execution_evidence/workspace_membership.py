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


WorkspaceMembershipStatus = Literal[
    "active",
    "suspended",
    "removed",
]


WorkspaceMembershipRole = Literal[
    "owner",
    "admin",
    "member",
    "viewer",
]


class WorkspaceMembership(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    membership_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    status: WorkspaceMembershipStatus
    role: Optional[WorkspaceMembershipRole] = None
    revision: int = Field(ge=0)
    created_by_principal_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    created_at: datetime
    updated_at: datetime
    status_changed_at: datetime

    @field_validator("membership_id")
    @classmethod
    def validate_membership_id(
        cls,
        value: str,
    ) -> str:
        prefix = "wsm_"

        if not value.startswith(prefix):
            raise ValueError(
                "Workspace membership IDs must "
                "start with 'wsm_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Workspace membership IDs must "
                "contain a valid UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Workspace membership IDs must "
                "contain a canonical UUID4."
            )

        return value

    @field_validator(
        "workspace_id",
        "principal_id",
        "created_by_principal_id",
    )
    @classmethod
    def reject_surrounding_whitespace(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        if value != value.strip():
            raise ValueError(
                "Workspace membership identity "
                "values must not contain surrounding "
                "whitespace."
            )

        return value

    @field_validator(
        "created_at",
        "updated_at",
        "status_changed_at",
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
                "Workspace membership timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_timestamp_order(
        self,
    ) -> "WorkspaceMembership":
        if self.updated_at < self.created_at:
            raise ValueError(
                "Workspace membership updated_at "
                "cannot precede created_at."
            )

        if (
            self.status_changed_at
            < self.created_at
        ):
            raise ValueError(
                "Workspace membership "
                "status_changed_at cannot precede "
                "created_at."
            )

        if (
            self.status_changed_at
            > self.updated_at
        ):
            raise ValueError(
                "Workspace membership "
                "status_changed_at cannot exceed "
                "updated_at."
            )

        return self


class WorkspaceMembershipRoleTransition(BaseModel):
    """Immutable post-creation membership role mutation.

    Membership creation owns revision zero through the
    existing status genesis transition. Role assignment,
    including trusted first-owner bootstrap, therefore
    always consumes current_revision + 1.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    transition_id: str = Field(min_length=1)
    membership_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)
    previous_role: Optional[
        WorkspaceMembershipRole
    ] = None
    new_role: WorkspaceMembershipRole
    previous_revision: int = Field(ge=0)
    resulting_revision: int = Field(ge=1)
    changed_at: datetime
    changed_by_principal_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    reason: Optional[str] = None

    @field_validator("transition_id")
    @classmethod
    def validate_role_transition_id(
        cls,
        value: str,
    ) -> str:
        prefix = "wmr_"

        if not value.startswith(prefix):
            raise ValueError(
                "Workspace membership role transition "
                "IDs must start with 'wmr_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Workspace membership role transition "
                "IDs must contain a valid UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Workspace membership role transition "
                "IDs must contain a canonical UUID4."
            )

        return value

    @field_validator(
        "membership_id",
        "workspace_id",
        "principal_id",
    )
    @classmethod
    def preserve_exact_role_transition_scope(
        cls,
        value: str,
    ) -> str:
        if not value:
            raise ValueError(
                "Membership role transition scope "
                "must be non-empty."
            )

        if value != value.strip():
            raise ValueError(
                "Membership role transition scope "
                "must not contain surrounding whitespace."
            )

        return value

    @field_validator("changed_at")
    @classmethod
    def require_role_transition_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Workspace membership role transition "
                "timestamps must be timezone-aware."
            )

        return value

    @field_validator("reason")
    @classmethod
    def normalize_role_transition_reason(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_role_transition(
        self,
    ) -> "WorkspaceMembershipRoleTransition":
        if self.previous_role == self.new_role:
            raise ValueError(
                "Workspace membership role "
                "self-transitions are not allowed."
            )

        if (
            self.resulting_revision
            != self.previous_revision + 1
        ):
            raise ValueError(
                "Workspace membership role transition "
                "revision must advance exactly once."
            )

        return self


def create_workspace_membership_role_transition_id(
) -> str:
    return f"wmr_{uuid4()}"


class WorkspaceMembershipTransition(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    transition_id: str = Field(min_length=1)
    membership_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    principal_id: str = Field(min_length=1)

    previous_status: Optional[
        WorkspaceMembershipStatus
    ] = None
    new_status: WorkspaceMembershipStatus

    previous_revision: Optional[int] = Field(
        default=None,
        ge=0,
    )
    resulting_revision: int = Field(ge=0)

    changed_at: datetime
    reason: Optional[str] = None

    @field_validator(
        "membership_id",
    )
    @classmethod
    def validate_membership_id(
        cls,
        value: str,
    ) -> str:
        WorkspaceMembership.model_fields[
            "membership_id"
        ]

        prefix = "wsm_"
        if not value.startswith(prefix):
            raise ValueError(
                "Workspace membership IDs must "
                "start with 'wsm_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Workspace membership IDs must "
                "contain a valid UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Workspace membership IDs must "
                "contain a canonical UUID4."
            )

        return value

    @field_validator(
        "workspace_id",
        "principal_id",
    )
    @classmethod
    def reject_surrounding_whitespace(
        cls,
        value: str,
    ) -> str:
        if value != value.strip():
            raise ValueError(
                "Workspace membership transition "
                "identity values must not contain "
                "surrounding whitespace."
            )

        return value

    @field_validator("changed_at")
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
                "Workspace membership transition "
                "timestamps must be timezone-aware."
            )

        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_revision_edge(
        self,
    ) -> "WorkspaceMembershipTransition":
        if self.previous_status is None:
            if (
                self.previous_revision is not None
                or self.new_status != "active"
                or self.resulting_revision != 0
            ):
                raise ValueError(
                    "Workspace membership genesis "
                    "transitions must create active "
                    "revision zero."
                )

            return self

        if self.previous_revision is None:
            raise ValueError(
                "Non-genesis membership transitions "
                "require a previous revision."
            )

        if self.previous_status == self.new_status:
            raise ValueError(
                "Workspace membership self-transitions "
                "are not allowed."
            )

        if (
            self.resulting_revision
            != self.previous_revision + 1
        ):
            raise ValueError(
                "Workspace membership transition "
                "revision must advance exactly once."
            )

        allowed = {
            "active": {
                "suspended",
                "removed",
            },
            "suspended": {
                "active",
                "removed",
            },
            "removed": set(),
        }

        if self.new_status not in allowed[
            self.previous_status
        ]:
            raise ValueError(
                "Workspace membership status "
                "transition is not allowed."
            )

        return self


class WorkspaceMembershipMutationResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    membership: WorkspaceMembership
    transition: WorkspaceMembershipTransition


def create_workspace_membership_id() -> str:
    return f"wsm_{uuid4()}"


def create_workspace_membership_transition_id() -> str:
    return f"wmt_{uuid4()}"
