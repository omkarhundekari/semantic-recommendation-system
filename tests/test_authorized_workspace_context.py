import pytest
from fastapi import HTTPException

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.workspace_access_service import (
    WorkspaceAccessNotFoundError,
    WorkspaceAccessStoreError,
)
from product_api import (
    get_authorized_workspace_context,
)


PRINCIPAL = AuthenticatedRequestPrincipal(
    principal_id=(
        "prn_123e4567-e89b-42d3-a456-426614174001"
    ),
    identity_provider_id=(
        "idp_123e4567-e89b-42d3-a456-426614174002"
    ),
    identity_link_id=(
        "pil_123e4567-e89b-42d3-a456-426614174003"
    ),
    issuer="https://issuer.example",
    subject="subject-123",
)

WORKSPACE_ID = "workspace-auth-test"
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174004"
)


class SuccessfulAccessService:
    def authorize(
        self,
        *,
        principal,
        workspace_id,
    ):
        return AuthorizedWorkspaceContext(
            principal_id=principal.principal_id,
            membership_id=MEMBERSHIP_ID,
            membership_role="admin",
            workspace_id=workspace_id,
        )


class MissingAccessService:
    def authorize(
        self,
        *,
        principal,
        workspace_id,
    ):
        raise WorkspaceAccessNotFoundError(
            "Workspace does not exist."
        )


class FailingAccessService:
    def authorize(
        self,
        *,
        principal,
        workspace_id,
    ):
        raise WorkspaceAccessStoreError(
            "Store failed."
        )


def test_authorized_workspace_context_returns_scope():
    context = get_authorized_workspace_context(
        workspace_id=WORKSPACE_ID,
        principal=PRINCIPAL,
        access_service=SuccessfulAccessService(),
    )

    assert context.workspace_id == WORKSPACE_ID
    assert context.principal_id == PRINCIPAL.principal_id
    assert context.membership_role == "admin"


def test_inaccessible_workspace_maps_to_404():
    with pytest.raises(HTTPException) as exc:
        get_authorized_workspace_context(
            workspace_id=WORKSPACE_ID,
            principal=PRINCIPAL,
            access_service=MissingAccessService(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Workspace does not exist."


def test_workspace_store_failure_maps_to_503():
    with pytest.raises(HTTPException) as exc:
        get_authorized_workspace_context(
            workspace_id=WORKSPACE_ID,
            principal=PRINCIPAL,
            access_service=FailingAccessService(),
        )

    assert exc.value.status_code == 503
