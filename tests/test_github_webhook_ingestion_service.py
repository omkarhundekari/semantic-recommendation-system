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
)
from execution_evidence.github_webhook_adapter import (
    GitHubWebhookPayloadError,
)
from execution_evidence.github_webhook_ingestion import (
    GitHubWebhookIngestionError,
    GitHubWebhookIngestionService,
    GitHubWebhookMalformedJSONError,
    GitHubWebhookPayloadShapeError,
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
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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

    assert store.appended_events == []


def test_ingest_rejects_malformed_json():
    store = RecordingExecutionEventStore()
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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
    first_service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=first_store,
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
    replay_service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=replay_store,
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
    service = GitHubWebhookIngestionService(
        secret=SECRET,
        event_store=store,
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
            event_store=store,
        )
