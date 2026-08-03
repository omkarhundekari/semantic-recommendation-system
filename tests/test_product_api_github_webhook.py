import asyncio
import json
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from execution_evidence.execution_event import (
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
    ExecutionEventProjectNotFoundError,
    ExecutionEventStoreError,
)
from execution_evidence.github_webhook_adapter import (
    GitHubWebhookPayloadError,
    adapt_github_webhook,
)
from execution_evidence.github_webhook_authenticated_source import (
    GitHubWebhookAuthenticatedSource,
)
from execution_evidence.github_webhook_authentication_service import (
    GitHubWebhookAuthenticationStoreError,
    GitHubWebhookCredentialAuthorityNotFoundError,
    GitHubWebhookEndpointNotFoundError,
    GitHubWebhookRepositoryIdentityError,
    GitHubWebhookSecretResolutionError,
)
from execution_evidence.github_webhook_ingestion import (
    GitHubWebhookMalformedJSONError,
    GitHubWebhookPayloadShapeError,
    GitHubWebhookRoutingNotFoundError,
    GitHubWebhookRoutingStoreError,
)
from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
)
from product_api import (
    MAX_GITHUB_WEBHOOK_BODY_BYTES,
    _read_bounded_github_webhook_body,
    app,
    get_github_webhook_authentication_service,
    get_github_webhook_ingestion_service,
)


RECORDED_AT = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
)

ENDPOINT_ID = (
    "gwe_123e4567-e89b-42d3-a456-426614174002"
)


def _push_payload() -> dict:
    return {
        "ref": "refs/heads/main",
        "before": "a" * 40,
        "after": "b" * 40,
        "created": False,
        "deleted": False,
        "forced": False,
        "repository": {
            "id": 123,
            "full_name": "owner/repository",
            "pushed_at": 1784635200,
        },
        "sender": {
            "id": 456,
            "login": "octocat",
        },
        "commits": [
            {
                "id": "b" * 40,
            }
        ],
    }


def _authenticated_source():
    return GitHubWebhookAuthenticatedSource(
        github_webhook_credential_id=(
            "gwc_123e4567-e89b-42d3-a456-426614174000"
        ),
        github_webhook_credential_authority_id=(
            "gwa_123e4567-e89b-42d3-a456-426614174001"
        ),
        webhook_endpoint_id=ENDPOINT_ID,
        repository_id="123",
    )


def _append_result(
    *,
    created: bool,
) -> ExecutionEventAppendResult:
    event = adapt_github_webhook(
        project_id="proj_test",
        event_name="push",
        delivery_id="delivery-123",
        recorded_at=RECORDED_AT,
        payload=_push_payload(),
    )

    return ExecutionEventAppendResult(
        event=event,
        created=created,
    )


class FakeGitHubWebhookAuthenticationService:
    def __init__(
        self,
        *,
        source=None,
        error=None,
    ):
        self.source = (
            source or _authenticated_source()
        )
        self.error = error
        self.calls = []

    def authenticate(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.source


class FakeGitHubWebhookIngestionService:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = (
            result
            if result is not None
            else _append_result(created=True)
        )
        self.error = error
        self.calls = []

    def ingest_authenticated(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _install_services(
    *,
    authentication_service=None,
    ingestion_service=None,
):
    authentication_service = (
        authentication_service
        or FakeGitHubWebhookAuthenticationService()
    )
    ingestion_service = (
        ingestion_service
        or FakeGitHubWebhookIngestionService()
    )

    app.dependency_overrides[
        get_github_webhook_authentication_service
    ] = lambda: authentication_service

    app.dependency_overrides[
        get_github_webhook_ingestion_service
    ] = lambda: ingestion_service

    return authentication_service, ingestion_service


def _post_webhook(
    client,
    *,
    endpoint_id=ENDPOINT_ID,
    body=None,
    headers=None,
):
    if body is None:
        body = json.dumps(
            _push_payload(),
            separators=(",", ":"),
        ).encode("utf-8")

    resolved_headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-123",
        "X-Hub-Signature-256": (
            "sha256=" + "a" * 64
        ),
    }

    if headers:
        resolved_headers.update(headers)

    return client.post(
        (
            "/v1/integrations/github/webhook/"
            f"{endpoint_id}"
        ),
        content=body,
        headers=resolved_headers,
    )


def test_webhook_endpoint_authenticates_then_ingests(
    client,
):
    authentication, ingestion = _install_services()

    raw_body = json.dumps(
        _push_payload(),
        separators=(",", ":"),
    ).encode("utf-8")

    response = _post_webhook(
        client,
        body=raw_body,
    )

    assert response.status_code == 200
    assert response.json()["created"] is True

    assert len(authentication.calls) == 1
    auth_call = authentication.calls[0]

    assert (
        auth_call["webhook_endpoint_id"]
        == ENDPOINT_ID
    )
    assert auth_call["signature_header"] == (
        "sha256=" + "a" * 64
    )
    assert auth_call["raw_body"] == raw_body

    assert len(ingestion.calls) == 1
    ingest_call = ingestion.calls[0]

    assert (
        ingest_call["authenticated_source"]
        == authentication.source
    )
    assert ingest_call["event_name"] == "push"
    assert ingest_call["delivery_id"] == (
        "delivery-123"
    )
    assert ingest_call["raw_body"] == raw_body
    assert (
        ingest_call["recorded_at"].tzinfo
        is not None
    )


def test_webhook_endpoint_returns_authoritative_replay(
    client,
):
    ingestion = FakeGitHubWebhookIngestionService(
        result=_append_result(created=False)
    )

    _install_services(
        ingestion_service=ingestion
    )

    response = _post_webhook(client)

    assert response.status_code == 200
    assert response.json()["created"] is False
    assert (
        response.json()["event"][
            "provider_idempotency_key"
        ]
        == "github:delivery:delivery-123"
    )


@pytest.mark.parametrize(
    "error",
    [
        GitHubWebhookEndpointNotFoundError(
            "unknown endpoint"
        ),
        GitHubWebhookCredentialAuthorityNotFoundError(
            "unauthorized repository"
        ),
    ],
)
def test_authentication_absence_is_indistinguishable(
    client,
    error,
):
    authentication = (
        FakeGitHubWebhookAuthenticationService(
            error=error
        )
    )

    authentication, ingestion = _install_services(
        authentication_service=authentication
    )

    response = _post_webhook(client)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "GitHub webhook source was not found.",
    }
    assert len(authentication.calls) == 1
    assert ingestion.calls == []


def test_routing_absence_has_same_public_response(
    client,
):
    ingestion = FakeGitHubWebhookIngestionService(
        error=GitHubWebhookRoutingNotFoundError(
            "repository not bound"
        )
    )

    _install_services(
        ingestion_service=ingestion
    )

    response = _post_webhook(client)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "GitHub webhook source was not found.",
    }


@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (
            GitHubWebhookSignatureError(
                "Signature verification failed."
            ),
            401,
        ),
        (
            GitHubWebhookRepositoryIdentityError(
                "Repository identity is invalid."
            ),
            422,
        ),
        (
            GitHubWebhookAuthenticationStoreError(
                "Authentication storage unavailable."
            ),
            503,
        ),
        (
            GitHubWebhookSecretResolutionError(
                "Secret unavailable."
            ),
            503,
        ),
    ],
)
def test_webhook_endpoint_maps_authentication_errors(
    client,
    error,
    status_code,
):
    authentication = (
        FakeGitHubWebhookAuthenticationService(
            error=error
        )
    )

    _, ingestion = _install_services(
        authentication_service=authentication
    )

    response = _post_webhook(client)

    assert response.status_code == status_code
    assert response.json() == {
        "detail": str(error),
    }
    assert ingestion.calls == []


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (
            GitHubWebhookMalformedJSONError(
                "Malformed JSON."
            ),
            422,
            "Malformed JSON.",
        ),
        (
            GitHubWebhookPayloadShapeError(
                "Payload must be an object."
            ),
            422,
            "Payload must be an object.",
        ),
        (
            GitHubWebhookPayloadError(
                "Unsupported GitHub webhook event."
            ),
            422,
            "Unsupported GitHub webhook event.",
        ),
        (
            ExecutionEventProjectNotFoundError(
                "Project was not found."
            ),
            404,
            "GitHub webhook source was not found.",
        ),
        (
            GitHubWebhookRoutingStoreError(
                "Trusted routing unavailable."
            ),
            503,
            "Trusted routing unavailable.",
        ),
        (
            ExecutionEventIdempotencyConflictError(
                "Delivery conflicts with stored event."
            ),
            409,
            "Delivery conflicts with stored event.",
        ),
        (
            ExecutionEventStoreError(
                "Execution event storage unavailable."
            ),
            503,
            "Execution event storage unavailable.",
        ),
    ],
)
def test_webhook_endpoint_maps_ingestion_errors(
    client,
    error,
    status_code,
    detail,
):
    ingestion = FakeGitHubWebhookIngestionService(
        error=error
    )

    _install_services(
        ingestion_service=ingestion
    )

    response = _post_webhook(client)

    assert response.status_code == status_code
    assert response.json() == {
        "detail": detail,
    }


@pytest.mark.parametrize(
    "missing_header",
    [
        "X-GitHub-Event",
        "X-GitHub-Delivery",
        "X-Hub-Signature-256",
    ],
)
def test_webhook_endpoint_requires_github_headers(
    client,
    missing_header,
):
    authentication, ingestion = _install_services()

    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-GitHub-Delivery": "delivery-123",
        "X-Hub-Signature-256": (
            "sha256=" + "a" * 64
        ),
    }

    del headers[missing_header]

    response = client.post(
        (
            "/v1/integrations/github/webhook/"
            f"{ENDPOINT_ID}"
        ),
        content=b"{}",
        headers=headers,
    )

    assert response.status_code == 422
    assert authentication.calls == []
    assert ingestion.calls == []


def test_legacy_project_webhook_route_is_removed(
    client,
):
    _install_services()

    response = client.post(
        (
            "/v1/projects/proj_test/"
            "execution-evidence/github/webhook"
        ),
        content=b"{}",
        headers={
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": "delivery-123",
            "X-Hub-Signature-256": (
                "sha256=" + "a" * 64
            ),
        },
    )

    assert response.status_code == 404


def test_declared_oversized_body_is_rejected(
    client,
):
    authentication, ingestion = _install_services()

    response = _post_webhook(
        client,
        body=b"{}",
        headers={
            "Content-Length": str(
                MAX_GITHUB_WEBHOOK_BODY_BYTES + 1
            ),
        },
    )

    assert response.status_code == 413
    assert authentication.calls == []
    assert ingestion.calls == []


def test_stream_limit_does_not_require_content_length():
    class StreamingRequest:
        headers = {}

        async def stream(self):
            yield (
                b"a"
                * MAX_GITHUB_WEBHOOK_BODY_BYTES
            )
            yield b"b"

    with pytest.raises(
        HTTPException
    ) as raised:
        asyncio.run(
            _read_bounded_github_webhook_body(
                StreamingRequest()
            )
        )

    assert raised.value.status_code == 413


def test_dependencies_require_trusted_sqlite_storage(
    client,
):
    from execution_evidence.json_store import (
        JsonRepositoryEvidenceStore,
    )
    from execution_evidence.storage_service import (
        ExecutionEvidenceStorageRuntime,
    )
    from product_api import (
        get_execution_evidence_storage_runtime,
    )

    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=JsonRepositoryEvidenceStore(
            "unused.json"
        ),
        trusted_sqlite_service=None,
        roadmap_registry=None,
        roadmap_registry_status=(
            "unavailable_legacy_store"
        ),
        remediation="Migrate to trusted SQLite.",
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime

    response = _post_webhook(client)

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "Durable execution event storage is "
            "unavailable. Migrate execution evidence "
            "storage to trusted SQLite."
        ),
    }
def test_webhook_end_to_end_uses_per_source_credential_authority_and_trusted_routing(
    client,
    monkeypatch,
    tmp_path,
):
    import hashlib
    import hmac

    from execution_evidence.github_source_binding import (
        GitHubSourceBinding,
    )
    from execution_evidence.github_webhook_credential import (
        GitHubWebhookCredential,
    )
    from execution_evidence.github_webhook_credential_authority import (
        GitHubWebhookCredentialAuthority,
    )
    from execution_evidence.sqlite_github_source_binding_store import (
        SQLiteGitHubSourceBindingStore,
    )
    from execution_evidence.sqlite_github_webhook_credential_authority_store import (
        SQLiteGitHubWebhookCredentialAuthorityStore,
    )
    from execution_evidence.sqlite_github_webhook_credential_store import (
        SQLiteGitHubWebhookCredentialStore,
    )
    from execution_evidence.sqlite_schema import (
        connect_execution_evidence_database,
    )
    from execution_evidence.storage_service import (
        ExecutionEvidenceStorageRuntime,
        TrustedSQLiteStorageService,
    )
    from execution_evidence.trusted_store import (
        initialize_fresh_trusted_store,
    )
    from product_api import (
        get_execution_evidence_storage_runtime,
    )

    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-08-03T20:00:00+00:00",
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                "workspace-secure",
                "2026-08-03T20:00:00+00:00",
                "2026-08-03T20:00:00+00:00",
            ),
        )

        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "project-secure",
                "workspace-secure",
                "Webhook trust-chain project",
                "active",
                "2026-08-03T20:00:00+00:00",
                "2026-08-03T20:00:00+00:00",
            ),
        )

        connection.execute("COMMIT")
    finally:
        connection.close()

    trusted_service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="local",
    )

    runtime = ExecutionEvidenceStorageRuntime(
        evidence_store=(
            trusted_service
            .build_repository_evidence_store()
        ),
        trusted_sqlite_service=trusted_service,
        roadmap_registry=(
            trusted_service
            .build_roadmap_snapshot_registry()
        ),
        roadmap_registry_status="ready",
        remediation=None,
    )

    app.dependency_overrides[
        get_execution_evidence_storage_runtime
    ] = lambda: runtime

    secret_ref = (
        "SOLVYN_GITHUB_WEBHOOK_E2E_SECRET"
    )
    secret = "per-source-e2e-secret"

    monkeypatch.setenv(
        secret_ref,
        secret,
    )

    credential = GitHubWebhookCredential(
        github_webhook_credential_id=(
            "gwc_123e4567-e89b-42d3-a456-426614174010"
        ),
        webhook_endpoint_id=(
            "gwe_123e4567-e89b-42d3-a456-426614174011"
        ),
        installation_id="9001",
        secret_ref=secret_ref,
        created_at=RECORDED_AT,
    )

    SQLiteGitHubWebhookCredentialStore(
        database_path
    ).create(credential)

    authority = GitHubWebhookCredentialAuthority(
        github_webhook_credential_authority_id=(
            "gwa_123e4567-e89b-42d3-a456-426614174012"
        ),
        github_webhook_credential_id=(
            credential.github_webhook_credential_id
        ),
        repository_id="123",
        created_at=RECORDED_AT,
    )

    SQLiteGitHubWebhookCredentialAuthorityStore(
        database_path
    ).create(authority)

    binding = GitHubSourceBinding(
        github_source_binding_id=(
            "gsb_123e4567-e89b-42d3-a456-426614174013"
        ),
        repository_id="123",
        installation_id="9001",
        workspace_id="workspace-secure",
        project_id="project-secure",
        created_at=RECORDED_AT,
    )

    SQLiteGitHubSourceBindingStore(
        database_path
    ).create(binding)

    raw_body = json.dumps(
        _push_payload(),
        separators=(",", ":"),
    ).encode("utf-8")

    digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    response = client.post(
        (
            "/v1/integrations/github/webhook/"
            f"{credential.webhook_endpoint_id}"
        ),
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": (
                "delivery-e2e-trusted-routing"
            ),
            "X-Hub-Signature-256": (
                f"sha256={digest}"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["created"] is True

    response_event = response.json()["event"]

    assert (
        response_event["project_id"]
        == "project-secure"
    )
    assert (
        response_event["provider_idempotency_key"]
        == (
            "github:delivery:"
            "delivery-e2e-trusted-routing"
        )
    )

    workspace_store = (
        trusted_service
        .build_execution_event_store_for_workspace(
            "workspace-secure"
        )
    )

    events = workspace_store.list_project_events(
        "project-secure"
    )

    assert len(events) == 1
    assert events[0].project_id == "project-secure"
    assert (
        events[0].provider_idempotency_key
        == (
            "github:delivery:"
            "delivery-e2e-trusted-routing"
        )
    )

    local_store = (
        trusted_service
        .build_execution_event_store_for_workspace(
            "local"
        )
    )

    assert (
        local_store.list_project_events(
            "project-secure"
        )
        == []
    )
