from datetime import datetime

import pytest
from pydantic import ValidationError

from execution_evidence.github_client import GitHubRateLimit
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
    GitHubSourceSyncObservation,
    GitHubSourceSyncSnapshot,
    update_github_sync_snapshot,
)


REPOSITORY_KEY = (
    "github:omkarhundekari/semantic-recommendation-system"
)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def test_successful_observation_records_etag_and_rate_limit():
    observed_at = _timestamp("2026-07-13T12:00:00Z")

    snapshot = update_github_sync_snapshot(
        previous=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
        ),
        observations=[
            GitHubSourceSyncObservation(
                evidence_type="commit",
                status="succeeded",
                observed_at=observed_at,
                etag='"commit-etag"',
                pages_fetched=2,
                rate_limit=GitHubRateLimit(
                    remaining=4990,
                    limit=5000,
                    resource="core",
                ),
            )
        ],
    )

    source = snapshot.sources["commit"]

    assert source.status == "succeeded"
    assert source.etag == '"commit-etag"'
    assert source.pages_fetched == 2
    assert source.last_attempted_at == observed_at
    assert source.last_succeeded_at == observed_at
    assert source.error_message is None
    assert source.rate_limit.remaining == 4990


def test_not_modified_preserves_previous_etag():
    previous_success = _timestamp(
        "2026-07-12T12:00:00Z"
    )
    observed_at = _timestamp(
        "2026-07-13T12:00:00Z"
    )

    snapshot = update_github_sync_snapshot(
        previous=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
            sources={
                "commit": GitHubSourceSyncSnapshot(
                    status="succeeded",
                    etag='"commit-etag"',
                    last_attempted_at=previous_success,
                    last_succeeded_at=previous_success,
                )
            },
        ),
        observations=[
            GitHubSourceSyncObservation(
                evidence_type="commit",
                status="not_modified",
                observed_at=observed_at,
            )
        ],
    )

    source = snapshot.sources["commit"]

    assert source.status == "not_modified"
    assert source.etag == '"commit-etag"'
    assert source.last_attempted_at == observed_at
    assert source.last_succeeded_at == observed_at


def test_failed_observation_preserves_last_success_and_etag():
    previous_success = _timestamp(
        "2026-07-12T12:00:00Z"
    )
    failed_at = _timestamp(
        "2026-07-13T12:00:00Z"
    )

    snapshot = update_github_sync_snapshot(
        previous=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
            sources={
                "workflow_run": GitHubSourceSyncSnapshot(
                    status="succeeded",
                    etag='"workflow-etag"',
                    last_attempted_at=previous_success,
                    last_succeeded_at=previous_success,
                )
            },
        ),
        observations=[
            GitHubSourceSyncObservation(
                evidence_type="workflow_run",
                status="failed",
                observed_at=failed_at,
                error_message="GitHub returned 403.",
                rate_limit=GitHubRateLimit(
                    remaining=0,
                ),
            )
        ],
    )

    source = snapshot.sources["workflow_run"]

    assert source.status == "failed"
    assert source.etag == '"workflow-etag"'
    assert source.last_attempted_at == failed_at
    assert source.last_succeeded_at == previous_success
    assert source.error_message == "GitHub returned 403."
    assert source.rate_limit.remaining == 0


def test_snapshot_exposes_only_available_etags():
    snapshot = GitHubRepositorySyncSnapshot(
        repository_key=REPOSITORY_KEY,
        sources={
            "commit": GitHubSourceSyncSnapshot(
                status="succeeded",
                etag='"commit-etag"',
            ),
            "release": GitHubSourceSyncSnapshot(
                status="never_synced",
            ),
        },
    )

    assert snapshot.etags() == {
        "commit": '"commit-etag"',
    }


def test_update_preserves_unobserved_source_states():
    release_state = GitHubSourceSyncSnapshot(
        status="succeeded",
        etag='"release-etag"',
    )

    snapshot = update_github_sync_snapshot(
        previous=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
            sources={
                "release": release_state,
            },
        ),
        observations=[
            GitHubSourceSyncObservation(
                evidence_type="commit",
                status="succeeded",
                observed_at=_timestamp(
                    "2026-07-13T12:00:00Z"
                ),
            )
        ],
    )

    assert snapshot.sources["release"] == release_state
    assert "commit" in snapshot.sources


def test_failed_observation_requires_error_message():
    with pytest.raises(ValidationError):
        GitHubSourceSyncObservation(
            evidence_type="commit",
            status="failed",
            observed_at=_timestamp(
                "2026-07-13T12:00:00Z"
            ),
        )


def test_successful_observation_rejects_error_message():
    with pytest.raises(ValidationError):
        GitHubSourceSyncObservation(
            evidence_type="commit",
            status="succeeded",
            observed_at=_timestamp(
                "2026-07-13T12:00:00Z"
            ),
            error_message="Unexpected error.",
        )
