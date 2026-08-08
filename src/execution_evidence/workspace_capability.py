from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import (
    FrozenSet,
    Mapping,
    Optional,
)

from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembershipRole,
)


class WorkspaceCapability(str, Enum):
    MEMBERSHIP_READ = "workspace.membership.read"
    MEMBERSHIP_ROLE_MANAGE = (
        "workspace.membership.role.manage"
    )
    MEMBERSHIP_STATUS_MANAGE = (
        "workspace.membership.status.manage"
    )


class WorkspaceAuthorizationRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


_VIEWER_CAPABILITIES = frozenset()

_MEMBER_CAPABILITIES = frozenset()

_MANAGER_CAPABILITIES = frozenset(
    {
        WorkspaceCapability.MEMBERSHIP_READ,
        WorkspaceCapability.MEMBERSHIP_ROLE_MANAGE,
        WorkspaceCapability.MEMBERSHIP_STATUS_MANAGE,
    }
)


ROLE_CAPABILITIES: Mapping[
    WorkspaceAuthorizationRole,
    FrozenSet[WorkspaceCapability],
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


class WorkspaceCapabilityDeniedError(
    RuntimeError
):
    pass


def capabilities_for_role(
    role: Optional[WorkspaceMembershipRole],
) -> FrozenSet[WorkspaceCapability]:
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


def require_workspace_capability(
    context: AuthorizedWorkspaceContext,
    capability: WorkspaceCapability,
) -> None:
    if not isinstance(
        context,
        AuthorizedWorkspaceContext,
    ):
        raise TypeError(
            "Authorized workspace context is required."
        )

    if not isinstance(
        capability,
        WorkspaceCapability,
    ):
        raise TypeError(
            "Workspace capability is required."
        )

    capabilities = capabilities_for_role(
        context.membership_role
    )

    if capability not in capabilities:
        raise WorkspaceCapabilityDeniedError(
            "Workspace capability is required: "
            f"{capability.value}."
        )
