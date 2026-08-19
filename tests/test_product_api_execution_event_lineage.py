from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_projection import (
    build_execution_event_lineage_projection,
)
from execution_evidence.execution_event_projection_service import (
    ExecutionEventProjectionUnsupportedStoreError,
)
from execution_evidence.execution_event_store import (
    ExecutionEventProjectHistoryTooLargeError,
    ExecutionEventProjectNotFoundError,
    StoredExecutionEvent,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
    ProjectAccessStoreError,
)
from execution_evidence.request_authenticator import (
    RequestAuthenticationFailedError,
    RequestAuthenticationRequiredError,
    RequestAuthenticationUnavailableError,
)
from product_api import (
    app,
    get_authorized_execution_event_projection_service,
    get_project_access_service,
    get_authentication_runtime,
)


BASE_TIME = datetime(
    2026,
    8,
    4,
    12,
    0,
    tzinfo=timezone.utc,
)

WORKSPACE_ID = "workspace-one"
PROJECT_ID = "project-test"

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174001"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174002"
)
MEMBERSHIP_ID = (
    "wsm_123e4567-e89b-42d3-a456-426614174003"
)


def _principal():
    return AuthenticatedRequestPrincipal(
        principal_id=PRINCIPAL_ID,
        identity_provider_id=PROVIDER_ID,
        identity_link_id=LINK_ID,
        issuer="https://issuer.example",
        subject="subject-123",
    )


def _context():
    return AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )


def _event_id(number: int) -> str:
    return (
        "evt_00000000-0000-4000-8000-"
        f"{number:012x}"
    )


def _record(
    number: int,
    *,
    sequence: int,
    supersedes: int | None = None,
) -> StoredExecutionEvent:
    return StoredExecutionEvent(
        store_sequence=sequence,
        event=ExecutionEvent(
            execution_event_id=_event_id(number),
            supersedes_execution_event_id=(
                _event_id(supersedes)
                if supersedes is not None
                else None
            ),
            project_id=PROJECT_ID,
            event_type="test.execution.event",
            occurred_at=BASE_TIME,
            recorded_at=BASE_TIME,
            source_provider="test",
            client_idempotency_key=(
                f"client-{number}"
            ),
            ingestion_method="system",
            payload={"number": number},
        ),
    )


class FakeAuthenticator:
    def __init__(
        self,
        *,
        principal=None,
        error=None,
    ):
        self.principal = principal or _principal()
        self.error = error
        self.headers = []

    def authenticate(self, header):
        self.headers.append(header)

        if self.error is not None:
            raise self.error

        return self.principal


class FakeProjectAccessService:
    def __init__(
        self,
        *,
        context=None,
        error=None,
    ):
        self.context = context or _context()
        self.error = error
        self.calls = []

    def authorize(
        self,
        *,
        principal,
        workspace_id,
        project_id,
    ):
        self.calls.append(
            (
                principal,
                workspace_id,
                project_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.context


class RecordingProjectionService:
    def __init__(
        self,
        projection,
        *,
        error=None,
    ):
        self.projection = projection
        self.error = error
        self.calls = []

    def project_lineage(self, project_id):
        self.calls.append(project_id)

        if self.error is not None:
            raise self.error

        return self.projection


def _path():
    return (
        f"/v1/workspaces/{WORKSPACE_ID}/"
        f"projects/{PROJECT_ID}/"
        "execution-evidence/events/lineage"
    )


def _install(
    *,
    authenticator=None,
    access_service=None,
    projection_service=None,
):
    if authenticator is not None:
        app.dependency_overrides[
            get_authentication_runtime
        ] = lambda: SimpleNamespace(
            ready=True,
            authenticator=authenticator,
        )

    if access_service is not None:
        app.dependency_overrides[
            get_project_access_service
        ] = lambda: access_service

    if projection_service is not None:
        app.dependency_overrides[
            get_authorized_execution_event_projection_service
        ] = lambda: projection_service


def _clear():
    app.dependency_overrides.clear()


def test_lineage_requires_authentication_before_authorization():
    authenticator = FakeAuthenticator(
        error=RequestAuthenticationRequiredError(
            "missing"
        )
    )
    access = FakeProjectAccessService()

    _install(
        authenticator=authenticator,
        access_service=access,
    )

    try:
        with TestClient(app) as client:
            response = client.get(_path())
    finally:
        _clear()

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"
    assert access.calls == []


def test_invalid_authentication_is_401():
    authenticator = FakeAuthenticator(
        error=RequestAuthenticationFailedError(
            "invalid"
        )
    )

    _install(
        authenticator=authenticator,
        access_service=FakeProjectAccessService(),
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer bad",
                },
            )
    finally:
        _clear()

    assert response.status_code == 401


def test_authentication_outage_is_503():
    authenticator = FakeAuthenticator(
        error=RequestAuthenticationUnavailableError(
            "jwks unavailable"
        )
    )

    _install(
        authenticator=authenticator,
        access_service=FakeProjectAccessService(),
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 503


def test_inaccessible_project_is_404():
    access = FakeProjectAccessService(
        error=ProjectAccessNotFoundError(
            "Project does not exist."
        )
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=access,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Project does not exist."
    )


def test_project_authorization_store_outage_is_503():
    access = FakeProjectAccessService(
        error=ProjectAccessStoreError(
            "database unavailable"
        )
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=access,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 503


def test_query_validation_occurs_after_authorization():
    access = FakeProjectAccessService(
        error=ProjectAccessNotFoundError(
            "Project does not exist."
        )
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=access,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                params={"limit": "50"},
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    # Unauthorized scope must not learn route-shape details
    # from query validation.
    assert response.status_code == 404


def test_lineage_uses_authorized_context_project():
    original = _record(
        1,
        sequence=4,
    )

    projection = (
        build_execution_event_lineage_projection(
            PROJECT_ID,
            [original],
        )
    )

    service = RecordingProjectionService(
        projection
    )
    access = FakeProjectAccessService()

    _install(
        authenticator=FakeAuthenticator(),
        access_service=access,
        projection_service=service,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 200

    assert access.calls == [
        (
            _principal(),
            WORKSPACE_ID,
            PROJECT_ID,
        )
    ]

    # Projection receives the authorized context's
    # project identity, not an independently selected ID.
    assert service.calls == [
        _context().project_id
    ]


@pytest.mark.parametrize(
    "parameter",
    [
        "limit",
        "cursor",
        "offset",
        "page",
        "page_size",
        "per_page",
        "before",
        "after",
    ],
)
def test_authorized_lineage_rejects_pagination(
    parameter,
):
    projection = (
        build_execution_event_lineage_projection(
            PROJECT_ID,
            [],
        )
    )
    service = RecordingProjectionService(
        projection
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=FakeProjectAccessService(),
        projection_service=service,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                params={parameter: "50"},
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    "parameter",
    [
        "from_sequence",
        "through_sequence",
    ],
)
def test_authorized_lineage_rejects_sequence_bounds(
    parameter,
):
    projection = (
        build_execution_event_lineage_projection(
            PROJECT_ID,
            [],
        )
    )
    service = RecordingProjectionService(
        projection
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=FakeProjectAccessService(),
        projection_service=service,
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                params={parameter: "10"},
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (
            ExecutionEventProjectionUnsupportedStoreError(
                "unsupported"
            ),
            503,
        ),
        (
            ExecutionEventProjectHistoryTooLargeError(
                "history too large"
            ),
            413,
        ),
        (
            ExecutionEventProjectNotFoundError(
                "missing"
            ),
            404,
        ),
    ],
)
def test_authorized_lineage_preserves_projection_errors(
    error,
    status,
):
    projection = (
        build_execution_event_lineage_projection(
            PROJECT_ID,
            [],
        )
    )

    _install(
        authenticator=FakeAuthenticator(),
        access_service=FakeProjectAccessService(),
        projection_service=RecordingProjectionService(
            projection,
            error=error,
        ),
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                _path(),
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        _clear()

    assert response.status_code == status


def test_old_project_only_lineage_route_is_not_exposed():
    with TestClient(app) as client:
        response = client.get(
            (
                f"/v1/projects/{PROJECT_ID}/"
                "execution-evidence/events/lineage"
            )
        )

    assert response.status_code == 404
