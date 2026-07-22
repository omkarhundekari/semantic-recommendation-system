from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import ValidationError

from execution_evidence.execution_event import (
    ExecutionEvent,
    create_execution_event_id,
)
from execution_evidence.execution_event_payload import (
    GitHubPullRequestMergedPayload,
    GitHubRefUpdatedPayload,
)


UTC = timezone.utc


class GitHubWebhookPayloadError(ValueError):
    pass


def adapt_github_pull_request_closed(
    *,
    project_id: str,
    delivery_id: str,
    recorded_at: datetime,
    payload: Dict[str, Any],
) -> ExecutionEvent:
    project_id = _required_identity_text(
        project_id,
        "project_id",
    )
    delivery_id = _required_identity_text(
        delivery_id,
        "delivery_id",
    )

    action = _required_text(
        payload,
        "action",
    )

    if action != "closed":
        raise GitHubWebhookPayloadError(
            "GitHub pull request action must "
            "be 'closed'."
        )

    pull_request = _required_mapping(
        payload,
        "pull_request",
    )
    repository = _required_mapping(
        payload,
        "repository",
    )
    sender = _required_mapping(
        payload,
        "sender",
    )

    merged = _required_boolean(
        pull_request,
        "merged",
        context="GitHub pull request",
    )

    if not merged:
        raise GitHubWebhookPayloadError(
            "GitHub pull request must be merged."
        )

    repository_id = str(
        _required_value(repository, "id")
    )
    sender_id = str(
        _required_value(sender, "id")
    )
    pull_request_id = str(
        _required_value(pull_request, "id")
    )

    pull_request_number = _required_positive_integer(
        pull_request,
        "number",
        context="GitHub pull request",
    )

    merge_commit_sha = _required_text(
        pull_request,
        "merge_commit_sha",
    )
    occurred_at = _parse_github_datetime(
        _required_text(
            pull_request,
            "merged_at",
        ),
        field_name="merged_at",
    )

    base = _required_mapping(
        pull_request,
        "base",
    )
    head = _required_mapping(
        pull_request,
        "head",
    )
    base_ref = _required_text(
        base,
        "ref",
    )
    head_ref = _required_text(
        head,
        "ref",
    )

    try:
        event_payload = GitHubPullRequestMergedPayload(
            repository_id=repository_id,
            pull_request_number=(
                pull_request_number
            ),
            base_ref=base_ref,
            head_ref=head_ref,
            merge_commit_sha=merge_commit_sha,
            sender_id=sender_id,
        )
    except ValidationError as error:
        raise GitHubWebhookPayloadError(
            "Invalid GitHub pull request payload."
        ) from error

    return ExecutionEvent(
        execution_event_id=(
            create_execution_event_id()
        ),
        project_id=project_id,
        event_type=(
            "github.pull_request.merged"
        ),
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        actor_id=sender_id,
        ingested_by_id="system_github",
        source_provider="github",
        source_account_id=sender_id,
        external_resource_id=repository_id,
        external_entity_type="pull_request",
        external_entity_id=pull_request_id,
        provider_idempotency_key=(
            f"github:delivery:{delivery_id}"
        ),
        ingestion_method="webhook",
        payload=event_payload,
    )


def adapt_github_push(
    *,
    project_id: str,
    delivery_id: str,
    recorded_at: datetime,
    payload: Dict[str, Any],
) -> ExecutionEvent:
    project_id = _required_identity_text(
        project_id,
        "project_id",
    )
    delivery_id = _required_identity_text(
        delivery_id,
        "delivery_id",
    )

    repository = _required_mapping(
        payload,
        "repository",
    )
    sender = _required_mapping(
        payload,
        "sender",
    )

    repository_id = str(
        _required_value(repository, "id")
    )
    sender_id = str(
        _required_value(sender, "id")
    )
    ref = _required_text(payload, "ref")
    before_sha = _required_text(
        payload,
        "before",
    )
    after_sha = _required_text(
        payload,
        "after",
    )

    commits = payload.get("commits", [])

    if not isinstance(commits, list):
        raise GitHubWebhookPayloadError(
            "GitHub push field 'commits' must "
            "be an array."
        )

    occurred_at = _parse_pushed_at(
        _required_value(
            repository,
            "pushed_at",
        )
    )

    created = _optional_boolean(
        payload,
        "created",
    )
    deleted = _optional_boolean(
        payload,
        "deleted",
    )
    forced = _optional_boolean(
        payload,
        "forced",
    )

    try:
        event_payload = GitHubRefUpdatedPayload(
            repository_id=repository_id,
            ref=ref,
            before_sha=before_sha,
            after_sha=after_sha,
            created=created,
            deleted=deleted,
            forced=forced,
            included_commit_count=len(commits),
            sender_id=sender_id,
        )
    except ValidationError as error:
        raise GitHubWebhookPayloadError(
            "Invalid GitHub push payload."
        ) from error

    return ExecutionEvent(
        execution_event_id=(
            create_execution_event_id()
        ),
        project_id=project_id,
        event_type="github.ref.updated",
        occurred_at=occurred_at,
        recorded_at=recorded_at,
        actor_id=sender_id,
        ingested_by_id="system_github",
        source_provider="github",
        source_account_id=sender_id,
        external_resource_id=repository_id,
        external_entity_type="git_ref",
        external_entity_id=ref,
        provider_idempotency_key=(
            f"github:delivery:{delivery_id}"
        ),
        ingestion_method="webhook",
        payload=event_payload,
    )


def _parse_github_datetime(
    value: str,
    *,
    field_name: str,
) -> datetime:
    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1] + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as error:
        raise GitHubWebhookPayloadError(
            f"GitHub field '{field_name}' must "
            "be a valid ISO-8601 datetime."
        ) from error

    if parsed.tzinfo is None:
        raise GitHubWebhookPayloadError(
            f"GitHub field '{field_name}' must "
            "include a timezone."
        )

    return parsed


def _required_boolean(
    payload: Dict[str, Any],
    field_name: str,
    *,
    context: str,
) -> bool:
    value = _required_value(
        payload,
        field_name,
    )

    if not isinstance(value, bool):
        raise GitHubWebhookPayloadError(
            f"{context} field '{field_name}' "
            "must be a boolean."
        )

    return value


def _required_positive_integer(
    payload: Dict[str, Any],
    field_name: str,
    *,
    context: str,
) -> int:
    value = _required_value(
        payload,
        field_name,
    )

    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < 1
    ):
        raise GitHubWebhookPayloadError(
            f"{context} field '{field_name}' "
            "must be a positive integer."
        )

    return value


def _optional_boolean(
    payload: Dict[str, Any],
    field_name: str,
) -> bool:
    value = payload.get(field_name, False)

    if not isinstance(value, bool):
        raise GitHubWebhookPayloadError(
            f"GitHub push field '{field_name}' "
            "must be a boolean."
        )

    return value


def _required_identity_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise GitHubWebhookPayloadError(
            f"GitHub webhook {field_name} must "
            "be non-empty text."
        )

    normalized = value.strip()

    if not normalized:
        raise GitHubWebhookPayloadError(
            f"GitHub webhook {field_name} must "
            "be non-empty text."
        )

    return normalized


def _required_mapping(
    payload: Dict[str, Any],
    key: str,
) -> Dict[str, Any]:
    value = payload.get(key)

    if not isinstance(value, dict):
        raise GitHubWebhookPayloadError(
            f"GitHub push field '{key}' must "
            "be an object."
        )

    return value


def _required_text(
    payload: Dict[str, Any],
    key: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str):
        raise GitHubWebhookPayloadError(
            f"GitHub push field '{key}' must "
            "be non-empty text."
        )

    value = value.strip()

    if not value:
        raise GitHubWebhookPayloadError(
            f"GitHub push field '{key}' must "
            "be non-empty text."
        )

    return value


def _required_value(
    payload: Dict[str, Any],
    key: str,
) -> Any:
    value = payload.get(key)

    if value is None or value == "":
        raise GitHubWebhookPayloadError(
            f"GitHub push field '{key}' is "
            "required."
        )

    return value


def _parse_pushed_at(
    value: Any,
) -> datetime:
    if isinstance(value, bool):
        raise GitHubWebhookPayloadError(
            "GitHub repository pushed_at must "
            "be a Unix timestamp."
        )

    try:
        timestamp = int(value)
    except (TypeError, ValueError) as error:
        raise GitHubWebhookPayloadError(
            "GitHub repository pushed_at must "
            "be a Unix timestamp."
        ) from error

    try:
        return datetime.fromtimestamp(
            timestamp,
            tz=UTC,
        )
    except (OverflowError, OSError, ValueError) as error:
        raise GitHubWebhookPayloadError(
            "GitHub repository pushed_at is "
            "outside the supported range."
        ) from error
