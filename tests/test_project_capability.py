from __future__ import annotations

from typing import cast

import pytest

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.project_capability import (
    ProjectCapability,
    ProjectCapabilityDeniedError,
    ROLE_CAPABILITIES,
    WorkspaceAuthorizationRole,
    capabilities_for_role,
    require_capability,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembershipRole,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)


def _context(
    *,
    membership_role=None,
) -> AuthorizedProjectContext:
    return AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role=membership_role,
        workspace_id="workspace-one",
        project_id="project-one",
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (
            "viewer",
            frozenset(
                {
                    ProjectCapability.PROJECT_READ,
                    ProjectCapability.EXECUTION_EVIDENCE_READ,
                }
            ),
        ),
        (
            "member",
            frozenset(
                {
                    ProjectCapability.PROJECT_READ,
                    ProjectCapability.EXECUTION_EVIDENCE_READ,
                    ProjectCapability.EXECUTION_EVIDENCE_MUTATE,
                }
            ),
        ),
        (
            "admin",
            frozenset(ProjectCapability),
        ),
        (
            "owner",
            frozenset(ProjectCapability),
        ),
    ],
)
def test_role_has_exact_capability_set(
    role,
    expected,
):
    assert capabilities_for_role(role) == expected


def test_unassigned_role_has_no_capabilities():
    assert capabilities_for_role(None) == frozenset()


def test_unknown_role_raises_instead_of_failing_silently():
    unknown = cast(
        WorkspaceMembershipRole,
        "superuser",
    )

    with pytest.raises(
        ValueError,
        match="Unknown workspace membership role",
    ):
        capabilities_for_role(unknown)


def test_role_capability_policy_is_immutable():
    with pytest.raises(TypeError):
        ROLE_CAPABILITIES[
            WorkspaceAuthorizationRole.VIEWER
        ] = frozenset()


def test_require_capability_rejects_non_context():
    with pytest.raises(
        TypeError,
        match="Authorized project context",
    ):
        require_capability(
            object(),
            ProjectCapability.PROJECT_READ,
        )


def test_require_capability_allows_present_capability():
    require_capability(
        _context(membership_role="viewer"),
        ProjectCapability.PROJECT_READ,
    )


def test_require_capability_denies_missing_capability():
    with pytest.raises(
        ProjectCapabilityDeniedError,
        match="project.lifecycle.manage",
    ):
        require_capability(
            _context(membership_role="viewer"),
            ProjectCapability.PROJECT_LIFECYCLE_MANAGE,
        )


def test_unassigned_context_is_denied():
    with pytest.raises(
        ProjectCapabilityDeniedError,
    ):
        require_capability(
            _context(),
            ProjectCapability.PROJECT_READ,
        )
