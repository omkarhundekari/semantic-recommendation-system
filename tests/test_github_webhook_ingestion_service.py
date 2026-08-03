import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import List, Optional

import pytest

from execution_evidence.execution_event import (
    ExecutionEvent,
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
    ExecutionEventStore,
    ExecutionEventStoreError,
)
from execution_evidence.github_webhook_adapter import (
    GitHubWebhookPayloadError,
)
from execution_evidence.github_webhook_ingestion import (
    GitHubWebhookIngestionError,
    GitHubWebhookIngestionService,
    GitHubWebhookMalformedJSONError,
    GitHubWebhookPayloadShapeError,
    GitHubWebhookProjectBindingMismatchError,
    GitHubWebhookRepositoryIdentityError,
    GitHubWebhookRoutingNotFoundError,
    GitHubWebhookRoutingStoreError,
)
from execution_evidence.github_source_routing import (
    GitHubSourceRoute,
)
from execution_evidence.github_source_routing_service import (
    GitHubSourceRoutingNotFoundError,
    GitHubSourceRoutingStoreError,
)
from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
)


UTC = timezone.utc
RECORDED_AT = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=UTC,
)
SECRET = b"github-webhook-secret"


class RecordingExecutionEventStore(
    ExecutionEventStore
):
    def __init__(
        self,
        *,
        append_result: Optional[
            ExecutionEventAppendResult
        ] = None,
        append_error: Optional[Exception] = None,
    ) -> None:
        self.appended_events: List[
            ExecutionEvent
        ] = []
        self._append_result = append_result
        self._append_error = append_error

    def append(
        self,
        event: ExecutionEvent,
    ) -> ExecutionEventAppendResult:
        self.appended_events.append(event)

        if self._append_error is not None:
            raise self._append_error

        if self._append_result is not None:
            return self._append_result

        return ExecutionEventAppendResult(
            event=event,
            created=True,
        )

    def load(
        self,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        return None

    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        return []


class RecordingRoutingService:
    def __init__(
        self,
        *,
        route: Optional[GitHubSourceRoute] = None,
        error: Optional[Exception] = None,
    ) -> None:
        self.route = route or GitHubSourceRoute(
            github_source_binding_id=(
                "gsb_123e4567-e89b-42d3-a456-426614174000"
            ),
            repository_id="123",
            workspace_id="workspace-b",
            project_id="proj_test",
        )
        self.error = error
        self.repository_ids = []

    def resolve(
        self,
        repository_id: str,
    ) -> GitHubSourceRoute:
        self.repository_ids.append(repository_id)

        if self.error is not None:
            raise self.error

        return self.route


class RecordingStoreFactory:
    def __init__(
        self,
        store: ExecutionEventStore,
        *,
        error: Optional[Exception] = None,
    ) -> None:
        self.store = store
        self.error = error
        self.workspace_ids = []

    def __call__(
        self,
        workspace_id: str,
    ) -> ExecutionEventStore:
        self.workspace_ids.append(workspace_id)

        if self.error is not None:
            raise self.error

        return self.store


def _service(
    *,
    store: Optional[
        RecordingExecutionEventStore
    ] = None,
    route: Optional[GitHubSourceRoute] = None,
    routing_error: Optional[Exception] = None,
    factory_error: Optional[Exception] = None,
):
    resolved_store = (
        store or RecordingExecutionEventStore()
    )
    routing = RecordingRoutingService(
        route=route,
        error=routing_error,
    )
    factory = RecordingStoreFactory(
        resolved_store,
        error=factory_error,
    )

    service = GitHubWebhookIngestionService(
        secret=SECRET,
        routing_service=routing,
        event_store_factory=factory,
    )

    return (
        service,
        resolved_store,
        routing,
        factory,
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
            "full_name": "owner/repo",
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


def _raw_body(
    payload: object,
) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(
    raw_body: bytes,
    *,
    secret: bytes = SECRET,
) -> str:
    digest = hmac.new(
        secret,
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def test_ingest_verifies_adapts_and_appends_event():
    store = RecordingExecutionEventStore()
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = _raw_body(_push_payload())

    result = service.ingest(
        project_id="proj_test",
        event_name="push",
        delivery_id="delivery-123",
        signature_header=_signature(raw_body),
        raw_body=raw_body,
        recorded_at=RECORDED_AT,
    )

    assert result.created is True
    assert result.event.event_type == (
        "github.ref.updated"
    )
    assert result.event.provider_idempotency_key == (
        "github:delivery:delivery-123"
    )
    assert store.appended_events == [result.event]


def test_ingest_rejects_invalid_signature_before_append():
    store = RecordingExecutionEventStore()
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookSignatureError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-123",
            signature_header=(
                "sha256=" + "0" * 64
            ),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert routing.repository_ids == []
    assert factory.workspace_ids == []
    assert store.appended_events == []


def test_ingest_rejects_malformed_json():
    store = RecordingExecutionEventStore()
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = b'{"broken":'

    with pytest.raises(
        GitHubWebhookMalformedJSONError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-123",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert routing.repository_ids == []
    assert factory.workspace_ids == []
    assert store.appended_events == []


@pytest.mark.parametrize(
    "payload",
    [
        [],
        "payload",
        123,
        True,
        None,
    ],
)
def test_ingest_requires_json_object_payload(
    payload: object,
):
    store = RecordingExecutionEventStore()
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = _raw_body(payload)

    with pytest.raises(
        GitHubWebhookPayloadShapeError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-123",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert store.appended_events == []


def test_ingest_propagates_unsupported_event_error():
    store = RecordingExecutionEventStore()
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookPayloadError,
        match="Unsupported GitHub webhook event",
    ):
        service.ingest(
            project_id="proj_test",
            event_name="repository",
            delivery_id="delivery-123",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert store.appended_events == []


def test_ingest_returns_authoritative_replay_result():
    first_store = RecordingExecutionEventStore()
    (
        first_service,
        first_store,
        first_routing,
        first_factory,
    ) = _service(
        store=first_store
    )
    raw_body = _raw_body(_push_payload())

    first_result = first_service.ingest(
        project_id="proj_test",
        event_name="push",
        delivery_id="delivery-123",
        signature_header=_signature(raw_body),
        raw_body=raw_body,
        recorded_at=RECORDED_AT,
    )

    replay_result = ExecutionEventAppendResult(
        event=first_result.event,
        created=False,
    )
    replay_store = RecordingExecutionEventStore(
        append_result=replay_result
    )
    (
        replay_service,
        replay_store,
        replay_routing,
        replay_factory,
    ) = _service(
        store=replay_store
    )

    result = replay_service.ingest(
        project_id="proj_test",
        event_name="push",
        delivery_id="delivery-123",
        signature_header=_signature(raw_body),
        raw_body=raw_body,
        recorded_at=RECORDED_AT,
    )

    assert result == replay_result
    assert result.created is False


def test_ingest_propagates_idempotency_conflict():
    conflict = (
        ExecutionEventIdempotencyConflictError(
            "conflicting delivery"
        )
    )
    store = RecordingExecutionEventStore(
        append_error=conflict
    )
    service, store, routing, factory = _service(
        store=store
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        ExecutionEventIdempotencyConflictError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-123",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )


def test_service_rejects_empty_secret():
    store = RecordingExecutionEventStore()

    with pytest.raises(
        GitHubWebhookIngestionError
    ):
        GitHubWebhookIngestionService(
            secret=b"",
            routing_service=RecordingRoutingService(),
            event_store_factory=RecordingStoreFactory(
                store
            ),
        )


def test_ingest_routes_by_trusted_repository_binding():
    service, store, routing, factory = _service()
    raw_body = _raw_body(_push_payload())

    result = service.ingest(
        project_id="proj_test",
        event_name="push",
        delivery_id="delivery-routing",
        signature_header=_signature(raw_body),
        raw_body=raw_body,
        recorded_at=RECORDED_AT,
    )

    assert result.created is True
    assert routing.repository_ids == ["123"]
    assert factory.workspace_ids == ["workspace-b"]
    assert len(store.appended_events) == 1
    assert (
        store.appended_events[0].project_id
        == "proj_test"
    )


def test_ingest_rejects_url_project_mismatch_before_append():
    route = GitHubSourceRoute(
        github_source_binding_id=(
            "gsb_123e4567-e89b-42d3-a456-426614174000"
        ),
        repository_id="123",
        workspace_id="workspace-b",
        project_id="proj_bound",
    )
    service, store, routing, factory = _service(
        route=route
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookProjectBindingMismatchError
    ):
        service.ingest(
            project_id="proj_url",
            event_name="push",
            delivery_id="delivery-mismatch",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert routing.repository_ids == ["123"]
    assert factory.workspace_ids == []
    assert store.appended_events == []


def test_ingest_unbound_repository_fails_closed():
    service, store, routing, factory = _service(
        routing_error=GitHubSourceRoutingNotFoundError(
            "not bound"
        )
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookRoutingNotFoundError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-unbound",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert factory.workspace_ids == []
    assert store.appended_events == []


def test_ingest_routing_store_failure_propagates():
    service, store, routing, factory = _service(
        routing_error=GitHubSourceRoutingStoreError(
            "routing unavailable"
        )
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookRoutingStoreError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-routing-error",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert factory.workspace_ids == []
    assert store.appended_events == []


def test_ingest_store_factory_failure_is_not_unresolved():
    service, store, routing, factory = _service(
        factory_error=ExecutionEventStoreError(
            "workspace store unavailable"
        )
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        GitHubWebhookRoutingStoreError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-store-error",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert factory.workspace_ids == ["workspace-b"]
    assert store.appended_events == []


def test_ingest_store_factory_programming_error_propagates():
    service, store, routing, factory = _service(
        factory_error=TypeError(
            "factory wiring bug"
        )
    )
    raw_body = _raw_body(_push_payload())

    with pytest.raises(
        TypeError,
        match="factory wiring bug",
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-factory-bug",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert routing.repository_ids == ["123"]
    assert factory.workspace_ids == ["workspace-b"]
    assert store.appended_events == []


@pytest.mark.parametrize(
    "repository_id",
    [
        None,
        "",
        "123",
        True,
        0,
        -1,
    ],
)
def test_ingest_requires_positive_integer_repository_identity(
    repository_id,
):
    service, store, routing, factory = _service()
    payload = _push_payload()
    payload["repository"]["id"] = repository_id
    raw_body = _raw_body(payload)

    with pytest.raises(
        GitHubWebhookRepositoryIdentityError
    ):
        service.ingest(
            project_id="proj_test",
            event_name="push",
            delivery_id="delivery-bad-repository",
            signature_header=_signature(raw_body),
            raw_body=raw_body,
            recorded_at=RECORDED_AT,
        )

    assert routing.repository_ids == []
    assert factory.workspace_ids == []
    assert store.appended_events == []
