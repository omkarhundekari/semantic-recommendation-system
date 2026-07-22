from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import pytest
from pydantic import ValidationError

from execution_evidence.execution_event import ExecutionEvent


OCCURRED_AT = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=timezone.utc,
)

RECORDED_AT = datetime(
    2026,
    7,
    22,
    12,
    0,
    1,
    tzinfo=timezone.utc,
)

EVENT_ID = "evt_11111111-1111-4111-8111-111111111111"
SUPERSEDED_EVENT_ID = (
    "evt_22222222-2222-4222-8222-222222222222"
)
OTHER_SUPERSEDED_EVENT_ID = (
    "evt_33333333-3333-4333-8333-333333333333"
)


def _event(
    *,
    execution_event_id: str = EVENT_ID,
    event_type: str = "github.workflow.completed",
    supersedes_execution_event_id: Optional[str] = None,
) -> ExecutionEvent:
    values = {
        "execution_event_id": execution_event_id,
        "project_id": "project-1",
        "event_type": event_type,
        "occurred_at": OCCURRED_AT,
        "recorded_at": RECORDED_AT,
        "actor_id": "github-user:456",
        "ingested_by_id": "system:github-webhook",
        "source_provider": "github",
        "source_account_id": "github-account:123",
        "provider_idempotency_key": (
            "github-delivery:delivery-1"
        ),
        "client_idempotency_key": None,
        "ingestion_method": "webhook",
        "source_payload_hash": "sha256:" + ("a" * 64),
        "verified_at": RECORDED_AT,
        "visibility": "private",
        "payload": {
            "repository_full_name": "owner/repository",
            "workflow_run_id": 789,
            "conclusion": "success",
        },
    }

    if supersedes_execution_event_id is not None:
        values["supersedes_execution_event_id"] = (
            supersedes_execution_event_id
        )

    return ExecutionEvent(**values)


def test_execution_event_allows_no_supersession_reference() -> None:
    event = _event()

    assert event.supersedes_execution_event_id is None


def test_execution_event_accepts_valid_supersession_reference() -> None:
    event = _event(
        supersedes_execution_event_id=SUPERSEDED_EVENT_ID,
    )

    assert (
        event.supersedes_execution_event_id
        == SUPERSEDED_EVENT_ID
    )


@pytest.mark.parametrize(
    "invalid_event_id",
    [
        "",
        "   ",
        "22222222-2222-4222-8222-222222222222",
        "event_22222222-2222-4222-8222-222222222222",
        "evt_not-a-uuid",
        "evt_22222222-2222-2222-2222-222222222222",
    ],
)
def test_execution_event_rejects_invalid_supersession_reference(
    invalid_event_id: str,
) -> None:
    with pytest.raises(ValidationError):
        _event(
            supersedes_execution_event_id=invalid_event_id,
        )


def test_execution_event_rejects_self_supersession() -> None:
    with pytest.raises(
        ValidationError,
        match="supersede itself",
    ):
        _event(
            execution_event_id=EVENT_ID,
            supersedes_execution_event_id=EVENT_ID,
        )


def test_supersession_target_participates_in_fingerprint() -> None:
    first = _event(
        supersedes_execution_event_id=SUPERSEDED_EVENT_ID,
    )
    second = _event(
        supersedes_execution_event_id=(
            OTHER_SUPERSEDED_EVENT_ID
        ),
    )

    assert (
        first.immutable_fingerprint()
        != second.immutable_fingerprint()
    )


def test_supersession_reference_survives_model_round_trip() -> None:
    original = _event(
        supersedes_execution_event_id=SUPERSEDED_EVENT_ID,
    )

    restored = ExecutionEvent.model_validate(
        original.model_dump(mode="json"),
    )

    assert (
        restored.supersedes_execution_event_id
        == SUPERSEDED_EVENT_ID
    )
    assert restored == original


def test_progression_event_does_not_require_supersession() -> None:
    event = _event(
        event_type="github.workflow.in_progress",
    )

    assert event.supersedes_execution_event_id is None


def test_valid_supersession_reference_contains_uuid() -> None:
    event = _event(
        supersedes_execution_event_id=SUPERSEDED_EVENT_ID,
    )

    raw_uuid = event.supersedes_execution_event_id.removeprefix(
        "evt_"
    )

    assert UUID(raw_uuid).version == 4
