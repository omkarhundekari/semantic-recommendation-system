from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import (
    FrozenSet,
    Mapping,
    Optional,
)

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembershipRole,
)


class ProjectCapability(str, Enum):
    PROJECT_READ = "project.read"
    EXECUTION_EVIDENCE_READ = (
        "execution_evidence.read"
    )
    EXECUTION_EVIDENCE_MUTATE = (
        "execution_evidence.mutate"
    )
    PROJECT_LIFECYCLE_MANAGE = (
        "project.lifecycle.manage"
    )
    WORKSPACE_MEMBERSHIP_READ = (
        "workspace.membership.read"
    )
    WORKSPACE_MEMBERSHIP_MANAGE = (
        "workspace.membership.manage"
    )


class WorkspaceAuthorizationRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


_VIEWER_CAPABILITIES = frozenset(
    {
        ProjectCapability.PROJECT_READ,
        ProjectCapability.EXECUTION_EVIDENCE_READ,
    }
)

_MEMBER_CAPABILITIES = frozenset(
    {
        *_VIEWER_CAPABILITIES,
        ProjectCapability.EXECUTION_EVIDENCE_MUTATE,
    }
)

_MANAGER_CAPABILITIES = frozenset(
    {
        ProjectCapability.PROJECT_READ,
        ProjectCapability.EXECUTION_EVIDENCE_READ,
        ProjectCapability.EXECUTION_EVIDENCE_MUTATE,
        ProjectCapability.PROJECT_LIFECYCLE_MANAGE,
        ProjectCapability.WORKSPACE_MEMBERSHIP_READ,
        ProjectCapability.WORKSPACE_MEMBERSHIP_MANAGE,
    }
)


ROLE_CAPABILITIES: Mapping[
    WorkspaceAuthorizationRole,
    FrozenSet[ProjectCapability],
] = MappingProxyType(
    {
        WorkspaceAuthorizationRole.VIEWER: (
            _VIEWER_CAPABILITIES
        ),
        WorkspaceAuthorizationRole.MEMBER: (
            _MEMBER_CAPABILITIES
        ),
        WorkspaceAuthorizationRole.ADMIN: (
            _MANAGER_CAPABILITIES
        ),
        WorkspaceAuthorizationRole.OWNER: (
            _MANAGER_CAPABILITIES
        ),
    }
)


class ProjectCapabilityDeniedError(
    RuntimeError
):
    pass


def capabilities_for_role(
    role: Optional[WorkspaceMembershipRole],
) -> FrozenSet[ProjectCapability]:
    if role is None:
        return frozenset()

    try:
        policy_role = WorkspaceAuthorizationRole(
            role
        )
    except ValueError as error:
        raise ValueError(
            "Unknown workspace membership role: "
            f"{role!r}."
        ) from error

    return ROLE_CAPABILITIES[policy_role]


def require_capability(
    context: AuthorizedProjectContext,
    capability: ProjectCapability,
) -> None:
    if not isinstance(
        context,
        AuthorizedProjectContext,
    ):
        raise TypeError(
            "Authorized project context is required."
        )

    if not isinstance(
        capability,
        ProjectCapability,
    ):
        raise TypeError(
            "Project capability is required."
        )

    capabilities = capabilities_for_role(
        context.membership_role
    )

    if capability not in capabilities:
        raise ProjectCapabilityDeniedError(
            "Project capability is required: "
            f"{capability.value}."
        )
