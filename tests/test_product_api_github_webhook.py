import json
from datetime import datetime, timezone

import pytest
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
from execution_evidence.github_webhook_ingestion import (
    GitHubWebhookMalformedJSONError,
    GitHubWebhookPayloadShapeError,
)
from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
)
from product_api import (
    app,
    get_github_webhook_ingestion_service,
)


RECORDED_AT = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=timezone.utc,
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


class FakeGitHubWebhookIngestionService:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def ingest(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _post_webhook(
    client,
    *,
    body: bytes = b'{"example":"payload"}',
    headers=None,
):
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
            "/v1/projects/proj_test/"
            "execution-evidence/github/webhook"
        ),
        content=body,
        headers=resolved_headers,
    )


def test_webhook_endpoint_preserves_raw_body_and_headers(
    client,
):
    result = _append_result(created=True)
    service = FakeGitHubWebhookIngestionService(
        result=result
    )

    app.dependency_overrides[
        get_github_webhook_ingestion_service
    ] = lambda: service

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
    assert (
        response.json()["event"]["event_type"]
        == "github.ref.updated"
    )

    assert len(service.calls) == 1
    call = service.calls[0]

    assert call["project_id"] == "proj_test"
    assert call["event_name"] == "push"
    assert call["delivery_id"] == "delivery-123"
    assert call["signature_header"] == (
        "sha256=" + "a" * 64
    )
    assert call["raw_body"] == raw_body
    assert call["recorded_at"].tzinfo is not None


def test_webhook_endpoint_returns_authoritative_replay(
    client,
):
    service = FakeGitHubWebhookIngestionService(
        result=_append_result(created=False)
    )

    app.dependency_overrides[
        get_github_webhook_ingestion_service
    ] = lambda: service

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
    ("error", "status_code"),
    [
        (
            GitHubWebhookSignatureError(
                "Signature verification failed."
            ),
            401,
        ),
        (
            GitHubWebhookMalformedJSONError(
                "Malformed JSON."
            ),
            422,
        ),
        (
            GitHubWebhookPayloadShapeError(
                "Payload must be an object."
            ),
            422,
        ),
        (
            GitHubWebhookPayloadError(
                "Unsupported GitHub webhook event."
            ),
            422,
        ),
        (
            ExecutionEventProjectNotFoundError(
                "Project was not found."
            ),
            404,
        ),
        (
            ExecutionEventIdempotencyConflictError(
                "Delivery conflicts with stored event."
            ),
            409,
        ),
        (
            ExecutionEventStoreError(
                "Execution event storage unavailable."
            ),
            503,
        ),
    ],
)
def test_webhook_endpoint_maps_domain_errors(
    client,
    error,
    status_code,
):
    service = FakeGitHubWebhookIngestionService(
        error=error
    )

    app.dependency_overrides[
        get_github_webhook_ingestion_service
    ] = lambda: service

    response = _post_webhook(client)

    assert response.status_code == status_code
    assert response.json() == {
        "detail": str(error),
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
    service = FakeGitHubWebhookIngestionService(
        result=_append_result(created=True)
    )

    app.dependency_overrides[
        get_github_webhook_ingestion_service
    ] = lambda: service

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
            "/v1/projects/proj_test/"
            "execution-evidence/github/webhook"
        ),
        content=b"{}",
        headers=headers,
    )

    assert response.status_code == 422
    assert service.calls == []


def test_webhook_dependency_requires_trusted_sqlite_storage(
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


def test_webhook_dependency_requires_configured_secret(
    client,
    monkeypatch,
    tmp_path,
):
    from execution_evidence.storage_service import (
        ExecutionEvidenceStorageRuntime,
        TrustedSQLiteStorageService,
    )
    from execution_evidence.trusted_store import (
        initialize_fresh_trusted_store,
    )
    from product_api import (
        GITHUB_WEBHOOK_SECRET_ENV,
        get_execution_evidence_storage_runtime,
    )

    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    trusted_service = TrustedSQLiteStorageService(
        database_path
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

    monkeypatch.delenv(
        GITHUB_WEBHOOK_SECRET_ENV,
        raising=False,
    )

    response = _post_webhook(client)

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "GitHub webhook ingestion is not "
            "configured."
        ),
    }


def test_webhook_dependency_rejects_blank_secret(
    client,
    monkeypatch,
    tmp_path,
):
    from execution_evidence.storage_service import (
        ExecutionEvidenceStorageRuntime,
        TrustedSQLiteStorageService,
    )
    from execution_evidence.trusted_store import (
        initialize_fresh_trusted_store,
    )
    from product_api import (
        GITHUB_WEBHOOK_SECRET_ENV,
        get_execution_evidence_storage_runtime,
    )

    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-22T12:00:00+00:00",
    )

    trusted_service = TrustedSQLiteStorageService(
        database_path
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

    monkeypatch.setenv(
        GITHUB_WEBHOOK_SECRET_ENV,
        "   ",
    )

    response = _post_webhook(client)

    assert response.status_code == 503
    assert response.json() == {
        "detail": (
            "GitHub webhook ingestion is not "
            "configured."
        ),
    }
