from datetime import datetime, timezone

import pytest

from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.workspace import (
    ProvisionedWorkspace,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipRoleTransition,
)
from execution_evidence.workspace_provisioning import (
    WorkspaceProvisioningError,
    WorkspaceProvisioningIdempotencyConflictError,
    WorkspaceProvisioningIdempotentResult,
    WorkspaceProvisioningPrincipalUnavailableError,
    WorkspaceProvisioningResult,
    WorkspaceProvisioningUnavailableError,
)
from product_api import (
    app,
    get_authenticated_request_principal,
    get_workspace_provisioning_service,
)


NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174001"
)
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174002"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174003"
)
WORKSPACE_ID = (
    "wsp_123e4567-e89b-42d3-a456-426614174004"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174005"
)
TRANSITION_ID = (
    "wmr_123e4567-e89b-42d3-a456-426614174006"
)


def _principal():
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://issuer.example",
        subject="subject-123",
    )


def _result(
    *,
    replayed: bool,
):
    result = WorkspaceProvisioningResult(
        workspace=ProvisionedWorkspace(
            workspace_id=WORKSPACE_ID,
            created_at=NOW,
            updated_at=NOW,
        ),
        membership=WorkspaceMembership(
            membership_id=MEMBERSHIP_ID,
            workspace_id=WORKSPACE_ID,
            principal_id=PRINCIPAL_ID,
            status="active",
            role="owner",
            revision=1,
            created_by_principal_id=PRINCIPAL_ID,
            created_at=NOW,
            updated_at=NOW,
            status_changed_at=NOW,
        ),
        owner_transition=(
            WorkspaceMembershipRoleTransition(
                transition_id=TRANSITION_ID,
                membership_id=MEMBERSHIP_ID,
                workspace_id=WORKSPACE_ID,
                principal_id=PRINCIPAL_ID,
                previous_role=None,
                new_role="owner",
                previous_revision=0,
                resulting_revision=1,
                changed_at=NOW,
                changed_by_principal_id=None,
                reason="self service",
            )
        ),
    )

    return WorkspaceProvisioningIdempotentResult(
        result=result,
        replayed=replayed,
    )


class FakeProvisioningService:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def provision_idempotent(
        self,
        *,
        principal_id,
        idempotency_key,
        created_at,
        reason=None,
    ):
        self.calls.append(
            {
                "principal_id": principal_id,
                "idempotency_key": idempotency_key,
                "created_at": created_at,
                "reason": reason,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


def _install(
    service: FakeProvisioningService,
):
    app.dependency_overrides[
        get_authenticated_request_principal
    ] = _principal

    app.dependency_overrides[
        get_workspace_provisioning_service
    ] = lambda: service


def _clear():
    app.dependency_overrides.clear()


def test_workspace_provisioning_returns_201_on_first_creation():
    service = FakeProvisioningService(
        result=_result(replayed=False)
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-create-1"
                    ),
                },
                json={
                    "reason": "self service",
                },
            )
    finally:
        _clear()

    assert response.status_code == 201
    assert (
        response.headers[
            "idempotency-replayed"
        ]
        == "false"
    )

    body = response.json()

    assert body["workspace"]["workspace_id"] == (
        WORKSPACE_ID
    )
    assert body["workspace"]["workspace_kind"] == (
        "provisioned"
    )
    assert body["membership"]["membership_id"] == (
        MEMBERSHIP_ID
    )
    assert body["membership"]["role"] == "owner"
    assert body["membership"]["revision"] == 1
    assert (
        body[
            "owner_transition"
        ]["transition_id"]
        == TRANSITION_ID
    )

    assert len(service.calls) == 1
    assert (
        service.calls[0]["principal_id"]
        == PRINCIPAL_ID
    )
    assert (
        service.calls[0]["idempotency_key"]
        == "workspace-create-1"
    )
    assert (
        service.calls[0]["reason"]
        == "self service"
    )
    assert (
        service.calls[0]["created_at"].tzinfo
        is not None
    )


def test_workspace_provisioning_returns_200_on_replay():
    service = FakeProvisioningService(
        result=_result(replayed=True)
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-replay-1"
                    ),
                },
                json={
                    "reason": "self service",
                },
            )
    finally:
        _clear()

    assert response.status_code == 200
    assert (
        response.headers[
            "idempotency-replayed"
        ]
        == "true"
    )
    assert (
        response.json()[
            "workspace"
        ]["workspace_id"]
        == WORKSPACE_ID
    )


def test_workspace_provisioning_requires_idempotency_key():
    service = FakeProvisioningService(
        result=_result(replayed=False)
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                json={},
            )
    finally:
        _clear()

    assert response.status_code == 422
    assert service.calls == []


def test_workspace_provisioning_maps_idempotency_conflict_to_409():
    service = FakeProvisioningService(
        error=(
            WorkspaceProvisioningIdempotencyConflictError(
                "conflict"
            )
        )
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-conflict"
                    ),
                },
                json={
                    "reason": "different",
                },
            )
    finally:
        _clear()

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Idempotency-Key was reused with "
            "different workspace provisioning "
            "request content."
        )
    }


def test_workspace_provisioning_maps_inactive_creation_principal_to_401():
    service = FakeProvisioningService(
        error=(
            WorkspaceProvisioningPrincipalUnavailableError(
                "inactive"
            )
        )
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-inactive"
                    ),
                },
                json={},
            )
    finally:
        _clear()

    assert response.status_code == 401
    assert (
        response.headers[
            "www-authenticate"
        ]
        == "Bearer"
    )
    assert response.json() == {
        "detail": "Authentication failed."
    }


def test_workspace_provisioning_maps_busy_storage_to_503():
    service = FakeProvisioningService(
        error=(
            WorkspaceProvisioningUnavailableError(
                "busy"
            )
        )
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-busy"
                    ),
                },
                json={},
            )
    finally:
        _clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Workspace provisioning storage is "
            "temporarily unavailable."
        )
    }


def test_workspace_provisioning_does_not_mislabel_unmapped_error_as_503():
    service = FakeProvisioningService(
        error=WorkspaceProvisioningError(
            "failure"
        )
    )
    _install(service)

    try:
        with pytest.raises(
            WorkspaceProvisioningError,
            match="failure",
        ):
            with TestClient(app) as client:
                client.post(
                    "/v1/workspaces",
                    headers={
                        "Idempotency-Key": (
                            "workspace-error"
                        ),
                    },
                    json={},
                )
    finally:
        app.dependency_overrides.clear()


def test_workspace_provisioning_maps_service_validation_to_422():
    service = FakeProvisioningService(
        error=ValueError(
            "Workspace provisioning idempotency key "
            "must be between 1 and 255 characters."
        )
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": "bad-key",
                },
                json={},
            )
    finally:
        _clear()

    assert response.status_code == 422
    assert (
        "between 1 and 255"
        in response.json()["detail"]
    )


def test_workspace_provisioning_request_rejects_extra_fields():
    service = FakeProvisioningService(
        result=_result(replayed=False)
    )
    _install(service)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/v1/workspaces",
                headers={
                    "Idempotency-Key": (
                        "workspace-extra"
                    ),
                },
                json={
                    "reason": "self service",
                    "workspace_id": (
                        "client-controlled"
                    ),
                },
            )
    finally:
        _clear()

    assert response.status_code == 422
    assert service.calls == []


def test_workspace_provisioning_replay_succeeds_after_durable_principal_deactivation(
    tmp_path,
):
    from datetime import (
        datetime,
        timezone,
    )

    from execution_evidence.authenticated_request_principal import (
        AuthenticatedRequestPrincipal,
    )
    from execution_evidence.principal import (
        Principal,
    )
    from execution_evidence.sqlite_principal_store import (
        SQLitePrincipalStore,
    )
    from execution_evidence.sqlite_schema import (
        connect_execution_evidence_database,
        initialize_execution_evidence_database,
    )
    from execution_evidence.workspace_provisioning import (
        SQLiteWorkspaceProvisioningService,
    )
    from product_api import (
        get_authenticated_request_principal,
        get_workspace_provisioning_service,
    )

    database_path = (
        tmp_path / "workspace-provisioning.db"
    )

    initialize_execution_evidence_database(
        database_path
    )

    principal_id = (
        "prn_123e4567-e89b-42d3-a456-426614174020"
    )

    now = datetime(
        2026,
        8,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    SQLitePrincipalStore(
        database_path
    ).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    authenticated_principal = (
        AuthenticatedRequestPrincipal(
            principal_id=principal_id,
            identity_provider_id=(
                "idp_123e4567-e89b-42d3-a456-426614174021"
            ),
            identity_link_id=(
                "pil_123e4567-e89b-42d3-a456-426614174022"
            ),
            issuer="https://issuer.example",
            subject=(
                "workspace-provisioning-replay-subject"
            ),
        )
    )

    provisioning_service = (
        SQLiteWorkspaceProvisioningService(
            database_path
        )
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = lambda: authenticated_principal

    app.dependency_overrides[
        get_workspace_provisioning_service
    ] = lambda: provisioning_service

    headers = {
        "Idempotency-Key": (
            "completed-before-principal-deactivation"
        ),
    }

    body = {
        "reason": (
            "durable principal replay regression"
        ),
    }

    try:
        with TestClient(app) as client:
            first = client.post(
                "/v1/workspaces",
                headers=headers,
                json=body,
            )

            assert first.status_code == 201
            assert (
                first.headers[
                    "Idempotency-Replayed"
                ]
                == "false"
            )

            first_payload = first.json()

            connection = (
                connect_execution_evidence_database(
                    database_path
                )
            )

            try:
                connection.execute(
                    """
                    UPDATE principals
                    SET
                        status = 'suspended',
                        updated_at = ?
                    WHERE principal_id = ?
                    """,
                    (
                        datetime(
                            2026,
                            8,
                            10,
                            12,
                            1,
                            tzinfo=timezone.utc,
                        ).isoformat(),
                        principal_id,
                    ),
                )

                stored_status = connection.execute(
                    """
                    SELECT status
                    FROM principals
                    WHERE principal_id = ?
                    """,
                    (principal_id,),
                ).fetchone()

                assert stored_status is not None
                assert (
                    stored_status["status"]
                    == "suspended"
                )
            finally:
                connection.close()

            replay = client.post(
                "/v1/workspaces",
                headers=headers,
                json=body,
            )
    finally:
        app.dependency_overrides.clear()

    assert replay.status_code == 200
    assert (
        replay.headers[
            "Idempotency-Replayed"
        ]
        == "true"
    )
    assert replay.json() == first_payload

