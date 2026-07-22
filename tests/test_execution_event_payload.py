import pytest
from pydantic import ValidationError

from execution_evidence.execution_event_payload import (
    ExecutionEventPayload,
    GitHubPullRequestMergedPayload,
    GitHubRefUpdatedPayload,
    validate_execution_event_payload,
)


def _github_ref_payload():
    return GitHubRefUpdatedPayload(
        repository_id="123",
        ref="refs/heads/main",
        before_sha="a" * 40,
        after_sha="b" * 40,
        created=False,
        deleted=False,
        forced=False,
        included_commit_count=2,
        sender_id="456",
    )


def test_registered_payload_matches_event_type():
    payload = _github_ref_payload()

    validated = validate_execution_event_payload(
        event_type="github.ref.updated",
        payload=payload,
    )

    assert validated is payload


def test_raw_dictionary_is_rejected():
    with pytest.raises(TypeError):
        validate_execution_event_payload(
            event_type="github.ref.updated",
            payload={
                "repository_id": "123",
                "ref": "refs/heads/main",
            },
        )


def test_wrong_registered_payload_type_is_rejected():
    payload = GitHubPullRequestMergedPayload(
        repository_id="123",
        pull_request_number=42,
        merge_commit_sha="c" * 40,
        base_ref="main",
        head_ref="feature",
        sender_id="456",
    )

    with pytest.raises(TypeError):
        validate_execution_event_payload(
            event_type="github.ref.updated",
            payload=payload,
        )


def test_unregistered_subclass_is_rejected():
    class UnsafePayload(ExecutionEventPayload):
        raw_body: dict

    payload = UnsafePayload(
        raw_body={"secret": "unsafe"},
    )

    with pytest.raises(TypeError):
        validate_execution_event_payload(
            event_type="github.ref.updated",
            payload=payload,
        )


def test_unknown_event_type_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported execution event type",
    ):
        validate_execution_event_payload(
            event_type="github.unknown",
            payload=_github_ref_payload(),
        )


def test_payload_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        GitHubRefUpdatedPayload(
            repository_id="123",
            ref="refs/heads/main",
            before_sha="a" * 40,
            after_sha="b" * 40,
            included_commit_count=1,
            sender_id="456",
            raw_webhook_body={"unsafe": True},
        )

from datetime import datetime, timezone

from execution_evidence.execution_event import ExecutionEvent


UTC = timezone.utc


def _execution_event(
    *,
    event_type,
    payload,
):
    return ExecutionEvent(
        execution_event_id="evt_test",
        project_id="proj_test",
        event_type=event_type,
        occurred_at=datetime(
            2026,
            7,
            21,
            12,
            0,
            tzinfo=UTC,
        ),
        recorded_at=datetime(
            2026,
            7,
            21,
            12,
            1,
            tzinfo=UTC,
        ),
        source_provider="github",
        provider_idempotency_key="github:test",
        ingestion_method="webhook",
        payload=payload,
    )


def test_execution_event_accepts_registered_typed_payload():
    payload = _github_ref_payload()

    event = _execution_event(
        event_type="github.ref.updated",
        payload=payload,
    )

    assert event.payload is payload


def test_execution_event_rejects_dictionary_for_registered_type():
    with pytest.raises(ValidationError):
        _execution_event(
            event_type="github.ref.updated",
            payload={
                "repository_id": "123",
                "ref": "refs/heads/main",
            },
        )


def test_execution_event_preserves_legacy_dictionary_payload():
    event = _execution_event(
        event_type="commit.created",
        payload={
            "repository": "owner/repository",
            "commit_sha": "abc",
        },
    )

    assert event.payload == {
        "repository": "owner/repository",
        "commit_sha": "abc",
    }



@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "ref": "main",
            },
            "ref",
        ),
        (
            {
                "before_sha": "abc",
            },
            "before_sha",
        ),
        (
            {
                "after_sha": "not-hex" * 6,
            },
            "after_sha",
        ),
        (
            {
                "created": True,
                "deleted": True,
                "before_sha": "0" * 40,
                "after_sha": "0" * 40,
            },
            "created and deleted",
        ),
        (
            {
                "created": True,
                "before_sha": "a" * 40,
            },
            "created ref",
        ),
        (
            {
                "deleted": True,
                "after_sha": "b" * 40,
            },
            "deleted ref",
        ),
        (
            {
                "deleted": True,
                "after_sha": "0" * 40,
                "included_commit_count": 1,
            },
            "deleted ref",
        ),
    ],
)
def test_github_ref_payload_rejects_invalid_semantics(
    changes,
    message,
):
    values = {
        "repository_id": "123",
        "ref": "refs/heads/main",
        "before_sha": "a" * 40,
        "after_sha": "b" * 40,
        "created": False,
        "deleted": False,
        "forced": False,
        "included_commit_count": 2,
        "sender_id": "456",
    }
    values.update(changes)

    with pytest.raises(
        ValidationError,
        match=message,
    ):
        GitHubRefUpdatedPayload(**values)


def test_github_created_ref_requires_zero_before_sha():
    payload = GitHubRefUpdatedPayload(
        repository_id="123",
        ref="refs/heads/feature",
        before_sha="0" * 40,
        after_sha="b" * 40,
        created=True,
        deleted=False,
        forced=False,
        included_commit_count=1,
        sender_id="456",
    )

    assert payload.created is True
    assert payload.before_sha == "0" * 40


def test_github_deleted_ref_requires_zero_after_sha():
    payload = GitHubRefUpdatedPayload(
        repository_id="123",
        ref="refs/heads/feature",
        before_sha="a" * 40,
        after_sha="0" * 40,
        created=False,
        deleted=True,
        forced=False,
        included_commit_count=0,
        sender_id="456",
    )

    assert payload.deleted is True
    assert payload.after_sha == "0" * 40
