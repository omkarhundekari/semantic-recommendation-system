import pytest

from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.workspace_capability import (
    ROLE_CAPABILITIES,
    WorkspaceAuthorizationRole,
    WorkspaceCapability,
    WorkspaceCapabilityDeniedError,
    capabilities_for_role,
    require_workspace_capability,
)


PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174001"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174002"
)
WORKSPACE_ID = "workspace-capability-test"


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (
            "owner",
            frozenset(
                {
                    WorkspaceCapability.MEMBERSHIP_READ,
                    WorkspaceCapability.MEMBERSHIP_ROLE_MANAGE,
                    WorkspaceCapability.MEMBERSHIP_STATUS_MANAGE,
                }
            ),
        ),
        (
            "admin",
            frozenset(
                {
                    WorkspaceCapability.MEMBERSHIP_READ,
                    WorkspaceCapability.MEMBERSHIP_ROLE_MANAGE,
                    WorkspaceCapability.MEMBERSHIP_STATUS_MANAGE,
                }
            ),
        ),
        ("member", frozenset()),
        ("viewer", frozenset()),
    ],
)
def test_role_has_exact_workspace_capabilities(
    role,
    expected,
):
    assert capabilities_for_role(role) == expected


def test_unassigned_role_has_no_capabilities():
    assert capabilities_for_role(None) == frozenset()


def test_unknown_role_raises():
    with pytest.raises(
        ValueError,
        match="Unknown workspace membership role",
    ):
        capabilities_for_role("unknown")


def test_role_capability_mapping_is_immutable():
    with pytest.raises(TypeError):
        ROLE_CAPABILITIES[
            WorkspaceAuthorizationRole.OWNER
        ] = frozenset()


def test_require_workspace_capability_rejects_bad_context():
    with pytest.raises(
        TypeError,
        match="Authorized workspace context",
    ):
        require_workspace_capability(
            object(),
            WorkspaceCapability.MEMBERSHIP_READ,
        )


def test_require_workspace_capability_rejects_bad_capability():
    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="owner",
        workspace_id=WORKSPACE_ID,
    )

    with pytest.raises(
        TypeError,
        match="Workspace capability",
    ):
        require_workspace_capability(
            context,
            object(),
        )


def test_missing_capability_raises_domain_error():
    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id=WORKSPACE_ID,
    )

    with pytest.raises(
        WorkspaceCapabilityDeniedError,
        match="workspace.membership.read",
    ):
        require_workspace_capability(
            context,
            WorkspaceCapability.MEMBERSHIP_READ,
        )


def test_manager_has_required_capability():
    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="admin",
        workspace_id=WORKSPACE_ID,
    )

    require_workspace_capability(
        context,
        WorkspaceCapability.MEMBERSHIP_STATUS_MANAGE,
    )
