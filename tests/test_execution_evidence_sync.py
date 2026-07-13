from datetime import datetime

import pytest
from pydantic import ValidationError

from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.sync import (
    GitHubSyncBatch,
    apply_github_sync,
)


REPOSITORY_KEY = (
    "github:omkarhundekari/semantic-recommendation-system"
)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _evidence(
    *,
    evidence_type: str,
    external_id: str,
    title: str,
    observed_at: str,
) -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=(
            "omkarhundekari/semantic-recommendation-system"
        ),
        evidence_type=evidence_type,
        external_id=external_id,
        title=title,
        url=(
            "https://github.com/omkarhundekari/"
            "semantic-recommendation-system"
        ),
        occurred_at=_timestamp(
            "2026-07-13T10:00:00Z"
        ),
        first_seen_at=_timestamp(observed_at),
        last_seen_at=_timestamp(observed_at),
    )


def _initial_state() -> RepositorySyncState:
    return RepositorySyncState(
        repository_key=REPOSITORY_KEY,
    )


def test_successful_sync_merges_all_batches_and_updates_state():
    attempted_at = _timestamp("2026-07-13T12:00:00Z")

    result = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=[],
        previous_state=_initial_state(),
        batches=[
            GitHubSyncBatch(
                evidence_type="commit",
                status="succeeded",
                items=[
                    _evidence(
                        evidence_type="commit",
                        external_id="abc123",
                        title="Add sync planner",
                        observed_at="2026-07-13T12:00:00Z",
                    )
                ],
            ),
            GitHubSyncBatch(
                evidence_type="pull_request",
                status="succeeded",
                items=[
                    _evidence(
                        evidence_type="pull_request",
                        external_id="42",
                        title="Merge sync planner",
                        observed_at="2026-07-13T12:00:00Z",
                    )
                ],
            ),
        ],
        attempted_at=attempted_at,
        latest_commit_sha="abc123",
        cursor="cursor-1",
    )

    assert result.status == "succeeded"
    assert len(result.evidence) == 2
    assert result.failed_types == []
    assert result.errors == {}
    assert result.synced_counts == {
        "commit": 1,
        "pull_request": 1,
    }

    assert result.sync_state.status == "succeeded"
    assert result.sync_state.last_attempted_at == attempted_at
    assert result.sync_state.last_succeeded_at == attempted_at
    assert result.sync_state.latest_commit_sha == "abc123"
    assert result.sync_state.cursor == "cursor-1"
    assert result.sync_state.error_message is None


def test_partial_sync_preserves_successful_evidence():
    attempted_at = _timestamp("2026-07-13T12:00:00Z")

    result = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=[],
        previous_state=_initial_state(),
        batches=[
            GitHubSyncBatch(
                evidence_type="commit",
                status="succeeded",
                items=[
                    _evidence(
                        evidence_type="commit",
                        external_id="abc123",
                        title="Add evidence sync",
                        observed_at="2026-07-13T12:00:00Z",
                    )
                ],
            ),
            GitHubSyncBatch(
                evidence_type="workflow_run",
                status="failed",
                error_message="GitHub returned 403.",
            ),
        ],
        attempted_at=attempted_at,
        latest_commit_sha="abc123",
    )

    assert result.status == "partially_succeeded"
    assert len(result.evidence) == 1
    assert result.evidence[0].external_id == "abc123"
    assert result.failed_types == ["workflow_run"]
    assert result.errors == {
        "workflow_run": "GitHub returned 403."
    }

    assert result.sync_state.status == "failed"
    assert result.sync_state.last_succeeded_at == attempted_at
    assert result.sync_state.latest_commit_sha == "abc123"
    assert (
        result.sync_state.error_message
        == "workflow_run: GitHub returned 403."
    )


def test_failed_sync_preserves_existing_evidence_and_cursor():
    previous_state = RepositorySyncState(
        repository_key=REPOSITORY_KEY,
        status="succeeded",
        latest_commit_sha="oldsha",
        cursor="cursor-old",
        last_attempted_at=_timestamp(
            "2026-07-12T12:00:00Z"
        ),
        last_succeeded_at=_timestamp(
            "2026-07-12T12:00:00Z"
        ),
    )

    existing = [
        _evidence(
            evidence_type="commit",
            external_id="oldsha",
            title="Existing evidence",
            observed_at="2026-07-12T12:00:00Z",
        )
    ]

    attempted_at = _timestamp("2026-07-13T12:00:00Z")

    result = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=existing,
        previous_state=previous_state,
        batches=[
            GitHubSyncBatch(
                evidence_type="commit",
                status="failed",
                error_message="Repository unavailable.",
            )
        ],
        attempted_at=attempted_at,
        latest_commit_sha="newsha",
        cursor="cursor-new",
    )

    assert result.status == "failed"
    assert result.evidence == existing
    assert result.sync_state.status == "failed"
    assert result.sync_state.last_attempted_at == attempted_at
    assert result.sync_state.last_succeeded_at == (
        previous_state.last_succeeded_at
    )
    assert result.sync_state.latest_commit_sha == "oldsha"
    assert result.sync_state.cursor == "cursor-old"


def test_repeated_successful_sync_is_idempotent():
    item = _evidence(
        evidence_type="commit",
        external_id="abc123",
        title="Add evidence sync",
        observed_at="2026-07-13T12:00:00Z",
    )

    batch = GitHubSyncBatch(
        evidence_type="commit",
        status="succeeded",
        items=[item],
    )

    first = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=[],
        previous_state=_initial_state(),
        batches=[batch],
        attempted_at=_timestamp(
            "2026-07-13T12:00:00Z"
        ),
    )

    second = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=first.evidence,
        previous_state=first.sync_state,
        batches=[batch],
        attempted_at=_timestamp(
            "2026-07-13T12:01:00Z"
        ),
    )

    assert len(second.evidence) == 1
    assert second.evidence[0].evidence_key == (
        first.evidence[0].evidence_key
    )


def test_empty_successful_batches_count_as_success():
    attempted_at = _timestamp("2026-07-13T12:00:00Z")

    result = apply_github_sync(
        repository_key=REPOSITORY_KEY,
        existing_evidence=[],
        previous_state=_initial_state(),
        batches=[
            GitHubSyncBatch(
                evidence_type="release",
                status="succeeded",
                items=[],
            )
        ],
        attempted_at=attempted_at,
    )

    assert result.status == "succeeded"
    assert result.evidence == []
    assert result.synced_counts == {"release": 0}
    assert result.sync_state.status == "succeeded"


def test_failed_batch_requires_error_message():
    with pytest.raises(ValidationError):
        GitHubSyncBatch(
            evidence_type="commit",
            status="failed",
        )


def test_failed_batch_rejects_items():
    with pytest.raises(ValidationError):
        GitHubSyncBatch(
            evidence_type="commit",
            status="failed",
            error_message="Request failed.",
            items=[
                _evidence(
                    evidence_type="commit",
                    external_id="abc123",
                    title="Should not be retained",
                    observed_at="2026-07-13T12:00:00Z",
                )
            ],
        )
