from datetime import datetime, timezone

import pytest

from execution_evidence.execution_event_payload import (
    GitHubPullRequestMergedPayload,
    GitHubRefUpdatedPayload,
)
from execution_evidence.github_webhook_adapter import (
    GitHubWebhookPayloadError,
    adapt_github_pull_request_closed,
    adapt_github_push,
)


UTC = timezone.utc
RECORDED_AT = datetime(
    2026,
    7,
    21,
    12,
    1,
    tzinfo=UTC,
)


def test_adapt_github_push_creates_typed_ref_update_event():
    event = adapt_github_push(
        project_id="proj_test",
        delivery_id="delivery-123",
        recorded_at=RECORDED_AT,
        payload={
            "ref": "refs/heads/main",
            "before": "a" * 40,
            "after": "b" * 40,
            "created": False,
            "deleted": False,
            "forced": False,
            "compare": (
                "https://github.com/owner/repo/"
                "compare/aaaaaaaa...bbbbbbbb"
            ),
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
                {"id": "b" * 40},
                {"id": "c" * 40},
            ],
        },
    )

    assert event.project_id == "proj_test"
    assert event.event_type == "github.ref.updated"
    assert event.source_provider == "github"
    assert event.source_account_id == "456"
    assert event.external_resource_id == "123"
    assert event.external_entity_type == "git_ref"
    assert event.external_entity_id == "refs/heads/main"
    assert event.provider_idempotency_key == (
        "github:delivery:delivery-123"
    )
    assert event.ingestion_method == "webhook"
    assert event.recorded_at == RECORDED_AT

    assert isinstance(
        event.payload,
        GitHubRefUpdatedPayload,
    )
    assert event.payload.repository_id == "123"
    assert event.payload.ref == "refs/heads/main"
    assert event.payload.before_sha == "a" * 40
    assert event.payload.after_sha == "b" * 40
    assert event.payload.included_commit_count == 2
    assert event.payload.sender_id == "456"


def test_adapt_github_push_supports_created_ref():
    event = adapt_github_push(
        project_id="proj_test",
        delivery_id="delivery-created",
        recorded_at=RECORDED_AT,
        payload={
            "ref": "refs/heads/feature",
            "before": "0" * 40,
            "after": "b" * 40,
            "created": True,
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
                {"id": "b" * 40},
            ],
        },
    )

    assert event.payload.created is True
    assert event.payload.deleted is False
    assert event.payload.before_sha == "0" * 40
    assert event.payload.after_sha == "b" * 40
    assert event.payload.included_commit_count == 1


def test_adapt_github_push_supports_deleted_ref():
    event = adapt_github_push(
        project_id="proj_test",
        delivery_id="delivery-deleted",
        recorded_at=RECORDED_AT,
        payload={
            "ref": "refs/heads/feature",
            "before": "a" * 40,
            "after": "0" * 40,
            "created": False,
            "deleted": True,
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
            "commits": [],
        },
    )

    assert event.payload.created is False
    assert event.payload.deleted is True
    assert event.payload.before_sha == "a" * 40
    assert event.payload.after_sha == "0" * 40
    assert event.payload.included_commit_count == 0


def test_adapt_github_push_rejects_non_list_commits():
    with pytest.raises(
        GitHubWebhookPayloadError,
        match="commits",
    ):
        adapt_github_push(
            project_id="proj_test",
            delivery_id="delivery-invalid",
            recorded_at=RECORDED_AT,
            payload={
                "ref": "refs/heads/main",
                "before": "a" * 40,
                "after": "b" * 40,
                "created": False,
                "deleted": False,
                "forced": False,
                "repository": {
                    "id": 123,
                    "pushed_at": 1784635200,
                },
                "sender": {
                    "id": 456,
                },
                "commits": {},
            },
        )


def test_adapt_github_push_wraps_invalid_ref_semantics():
    with pytest.raises(
        GitHubWebhookPayloadError,
        match="Invalid GitHub push payload",
    ):
        adapt_github_push(
            project_id="proj_test",
            delivery_id="delivery-invalid-ref",
            recorded_at=RECORDED_AT,
            payload={
                "ref": "main",
                "before": "a" * 40,
                "after": "b" * 40,
                "created": False,
                "deleted": False,
                "forced": False,
                "repository": {
                    "id": 123,
                    "pushed_at": 1784635200,
                },
                "sender": {
                    "id": 456,
                },
                "commits": [],
            },
        )


@pytest.mark.parametrize(
    ("project_id", "delivery_id", "message"),
    [
        ("", "delivery-123", "project_id"),
        ("proj_test", "", "delivery_id"),
        ("   ", "delivery-123", "project_id"),
        ("proj_test", "   ", "delivery_id"),
    ],
)
def test_adapt_github_push_rejects_blank_identity_inputs(
    project_id,
    delivery_id,
    message,
):
    with pytest.raises(
        GitHubWebhookPayloadError,
        match=message,
    ):
        adapt_github_push(
            project_id=project_id,
            delivery_id=delivery_id,
            recorded_at=RECORDED_AT,
            payload={
                "ref": "refs/heads/main",
                "before": "a" * 40,
                "after": "b" * 40,
                "created": False,
                "deleted": False,
                "forced": False,
                "repository": {
                    "id": 123,
                    "pushed_at": 1784635200,
                },
                "sender": {
                    "id": 456,
                },
                "commits": [],
            },
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "created",
        "deleted",
        "forced",
    ],
)
def test_adapt_github_push_rejects_non_boolean_flags(
    field_name,
):
    payload = {
        "ref": "refs/heads/main",
        "before": "a" * 40,
        "after": "b" * 40,
        "created": False,
        "deleted": False,
        "forced": False,
        "repository": {
            "id": 123,
            "pushed_at": 1784635200,
        },
        "sender": {
            "id": 456,
        },
        "commits": [],
    }
    payload[field_name] = "false"

    with pytest.raises(
        GitHubWebhookPayloadError,
        match=field_name,
    ):
        adapt_github_push(
            project_id="proj_test",
            delivery_id=(
                f"delivery-invalid-{field_name}"
            ),
            recorded_at=RECORDED_AT,
            payload=payload,
        )


def test_adapt_github_pull_request_merged():
    event = adapt_github_pull_request_closed(
        project_id="proj_test",
        delivery_id="delivery-pr",
        recorded_at=RECORDED_AT,
        payload={
            "action": "closed",
            "pull_request": {
                "id": 12345,
                "number": 27,
                "merged": True,
                "merged_at": "2026-07-21T18:30:00Z",
                "merge_commit_sha": "a" * 40,
                "base": {
                    "ref": "main",
                },
                "head": {
                    "ref": "feature/evidence",
                },
            },
            "repository": {
                "id": 987,
            },
            "sender": {
                "id": 456,
            },
        },
    )

    assert event.event_type == "github.pull_request.merged"

    payload = event.payload

    assert isinstance(
        payload,
        GitHubPullRequestMergedPayload,
    )

    assert payload.repository_id == "987"
    assert payload.pull_request_number == 27
    assert payload.base_ref == "main"
    assert payload.head_ref == "feature/evidence"
    assert payload.merge_commit_sha == "a" * 40
    assert payload.sender_id == "456"

    assert event.external_entity_id == "12345"


def test_adapt_github_pull_request_closed_rejects_unmerged_pull_request():
    with pytest.raises(
        GitHubWebhookPayloadError,
        match="must be merged",
    ):
        adapt_github_pull_request_closed(
            project_id="proj_test",
            delivery_id="delivery-pr-unmerged",
            recorded_at=RECORDED_AT,
            payload={
                "action": "closed",
                "pull_request": {
                    "id": 12345,
                    "number": 27,
                    "merged": False,
                    "merge_commit_sha": None,
                    "base": {
                        "ref": "main",
                    },
                    "head": {
                        "ref": "feature/evidence",
                    },
                },
                "repository": {
                    "id": 987,
                },
                "sender": {
                    "id": 456,
                },
            },
        )


def test_adapt_github_pull_request_uses_merged_at_as_occurred_at():
    merged_at = datetime(
        2026,
        7,
        21,
        18,
        30,
        tzinfo=timezone.utc,
    )
    recorded_at = datetime(
        2026,
        7,
        21,
        18,
        35,
        tzinfo=timezone.utc,
    )

    event = adapt_github_pull_request_closed(
        project_id="proj_test",
        delivery_id="delivery-pr-time",
        recorded_at=recorded_at,
        payload={
            "action": "closed",
            "pull_request": {
                "id": 12345,
                "number": 27,
                "merged": True,
                "merged_at": "2026-07-21T18:30:00Z",
                "merge_commit_sha": "a" * 40,
                "base": {
                    "ref": "main",
                },
                "head": {
                    "ref": "feature/evidence",
                },
            },
            "repository": {
                "id": 987,
            },
            "sender": {
                "id": 456,
            },
        },
    )

    assert event.occurred_at == merged_at
    assert event.recorded_at == recorded_at


def test_adapt_github_issue_closed():
    from execution_evidence.github_webhook_adapter import (
        adapt_github_issue_closed,
    )

    event = adapt_github_issue_closed(
        project_id="proj_test",
        delivery_id="delivery-issue",
        recorded_at=RECORDED_AT,
        payload={
            "action": "closed",
            "issue": {
                "id": 555,
                "number": 42,
                "title": "Finish execution evidence",
                "closed_at": "2026-07-21T19:00:00Z",
            },
            "repository": {
                "id": 987,
            },
            "sender": {
                "id": 456,
            },
        },
    )

    assert event.event_type == "github.issue.closed"
    assert event.external_entity_id == "555"
    assert event.payload.repository_id == "987"
    assert event.payload.issue_number == 42
    assert event.payload.title == "Finish execution evidence"
    assert event.payload.sender_id == "456"
    assert event.occurred_at == datetime(
        2026,
        7,
        21,
        19,
        0,
        tzinfo=timezone.utc,
    )
    assert event.recorded_at == RECORDED_AT


def test_adapt_github_issue_closed_rejects_non_closed_action():
    from execution_evidence.github_webhook_adapter import (
        adapt_github_issue_closed,
    )

    with pytest.raises(GitHubWebhookPayloadError):
        adapt_github_issue_closed(
            project_id="proj_test",
            delivery_id="delivery-issue",
            recorded_at=RECORDED_AT,
            payload={
                "action": "edited",
                "issue": {
                    "id": 555,
                    "number": 42,
                    "title": "Finish execution evidence",
                    "closed_at": "2026-07-21T19:00:00Z",
                },
                "repository": {
                    "id": 987,
                },
                "sender": {
                    "id": 456,
                },
            },
        )
