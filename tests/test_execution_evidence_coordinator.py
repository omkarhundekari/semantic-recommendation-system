from datetime import datetime
from typing import Optional

import pytest

from execution_evidence.coordinator import (
    StatefulGitHubSyncCoordinator,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
    GitHubSourceSyncSnapshot,
)
from execution_evidence.store import (
    InMemoryRepositoryEvidenceStore,
    RepositoryEvidenceConflictError,
    StoredRepositoryEvidence,
)
from execution_evidence.sync import GitHubSyncResult


REPOSITORY_URL = (
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

REPOSITORY_KEY = (
    "github:omkarhundekari/semantic-recommendation-system"
)

OBSERVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)


def _evidence(
    *,
    external_id: str,
    observed_at: datetime,
) -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=(
            "omkarhundekari/"
            "semantic-recommendation-system"
        ),
        evidence_type="commit",
        external_id=external_id,
        title="Add stateful sync coordination",
        url=(
            "https://github.com/omkarhundekari/"
            "semantic-recommendation-system/commit/"
            f"{external_id}"
        ),
        occurred_at=observed_at,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


class FakeSyncService:
    def __init__(
        self,
        *,
        result: Optional[GitHubSyncResult] = None,
    ) -> None:
        self.result = result
        self.calls = []

    def sync_repository(self, **kwargs):
        self.calls.append(kwargs)

        if self.result is not None:
            return self.result

        previous_state = kwargs["previous_state"]
        previous_snapshot = kwargs["previous_snapshot"]
        observed_at = kwargs["observed_at"]

        evidence = [
            *kwargs["existing_evidence"],
            _evidence(
                external_id="abc123",
                observed_at=observed_at,
            ),
        ]

        updated_snapshot = previous_snapshot.model_copy(
            update={
                "sources": {
                    **previous_snapshot.sources,
                    "commit": GitHubSourceSyncSnapshot(
                        status="succeeded",
                        etag='"commit-etag"',
                        pages_fetched=1,
                        last_attempted_at=observed_at,
                        last_succeeded_at=observed_at,
                    ),
                }
            }
        )

        return GitHubSyncResult(
            repository_key=REPOSITORY_KEY,
            status="succeeded",
            evidence=evidence,
            sync_state=previous_state.model_copy(
                update={
                    "status": "succeeded",
                    "latest_commit_sha": "abc123",
                    "last_attempted_at": observed_at,
                    "last_succeeded_at": observed_at,
                }
            ),
            sync_snapshot=updated_snapshot,
            synced_counts={"commit": 1},
            failed_types=[],
            errors={},
        )


def test_coordinator_initializes_and_saves_new_repository():
    store = InMemoryRepositoryEvidenceStore()
    service = FakeSyncService()

    coordinator = StatefulGitHubSyncCoordinator(
        service=service,
        store=store,
    )

    result = coordinator.sync_repository(
        repository_url=REPOSITORY_URL,
        observed_at=OBSERVED_AT,
    )

    assert result.created is True
    assert result.stored.revision == 0
    assert len(result.stored.evidence) == 1
    assert (
        result.stored.sync_state.latest_commit_sha
        == "abc123"
    )
    assert (
        result.stored.sync_snapshot.sources[
            "commit"
        ].etag
        == '"commit-etag"'
    )

    loaded = store.load(REPOSITORY_KEY)

    assert loaded == result.stored


def test_coordinator_reuses_existing_aggregate():
    store = InMemoryRepositoryEvidenceStore()

    existing_time = datetime.fromisoformat(
        "2026-07-12T12:00:00+00:00"
    )

    existing = StoredRepositoryEvidence(
        repository=(
            __import__(
                "execution_evidence.github_repository",
                fromlist=["parse_github_repository_url"],
            ).parse_github_repository_url(
                REPOSITORY_URL
            )
        ),
        evidence=[
            _evidence(
                external_id="oldsha",
                observed_at=existing_time,
            )
        ],
        sync_state=RepositorySyncState(
            repository_key=REPOSITORY_KEY,
            status="succeeded",
            latest_commit_sha="oldsha",
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
            sources={
                "commit": GitHubSourceSyncSnapshot(
                    status="succeeded",
                    etag='"old-etag"',
                )
            },
        ),
        saved_at=existing_time,
    )

    first_saved = store.save(existing)
    service = FakeSyncService()

    coordinator = StatefulGitHubSyncCoordinator(
        service=service,
        store=store,
    )

    result = coordinator.sync_repository(
        repository_url=REPOSITORY_URL,
        observed_at=OBSERVED_AT,
        since="2026-07-12T12:00:00Z",
    )

    assert result.created is False
    assert result.stored.revision == 1
    assert {
        item.external_id
        for item in result.stored.evidence
    } == {
        "oldsha",
        "abc123",
    }

    call = service.calls[0]

    assert call["existing_evidence"] == (
        first_saved.evidence
    )
    assert call["previous_state"] == (
        first_saved.sync_state
    )
    assert call["previous_snapshot"] == (
        first_saved.sync_snapshot
    )
    assert (
        call["since"]
        == "2026-07-12T12:00:00Z"
    )


def test_coordinator_persists_partial_sync_result():
    store = InMemoryRepositoryEvidenceStore()

    partial_result = GitHubSyncResult(
        repository_key=REPOSITORY_KEY,
        status="partially_succeeded",
        evidence=[
            _evidence(
                external_id="abc123",
                observed_at=OBSERVED_AT,
            )
        ],
        sync_state=RepositorySyncState(
            repository_key=REPOSITORY_KEY,
            status="failed",
            latest_commit_sha="abc123",
            last_attempted_at=OBSERVED_AT,
            last_succeeded_at=OBSERVED_AT,
            error_message=(
                "workflow_run: GitHub returned 403."
            ),
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
            sources={
                "workflow_run": GitHubSourceSyncSnapshot(
                    status="failed",
                    error_message=(
                        "GitHub returned 403."
                    ),
                    last_attempted_at=OBSERVED_AT,
                )
            },
        ),
        synced_counts={"commit": 1},
        failed_types=["workflow_run"],
        errors={
            "workflow_run": "GitHub returned 403."
        },
    )

    coordinator = StatefulGitHubSyncCoordinator(
        service=FakeSyncService(
            result=partial_result
        ),
        store=store,
    )

    result = coordinator.sync_repository(
        repository_url=REPOSITORY_URL,
        observed_at=OBSERVED_AT,
    )

    assert result.sync.status == (
        "partially_succeeded"
    )
    assert result.stored.sync_state.status == "failed"
    assert (
        result.stored.sync_snapshot.sources[
            "workflow_run"
        ].status
        == "failed"
    )
    assert len(result.stored.evidence) == 1


def test_coordinator_surfaces_revision_conflict():
    class ConflictingStore(
        InMemoryRepositoryEvidenceStore
    ):
        def save(
            self,
            record,
            *,
            expected_revision=None,
        ):
            raise RepositoryEvidenceConflictError(
                "Forced revision conflict."
            )

    coordinator = StatefulGitHubSyncCoordinator(
        service=FakeSyncService(),
        store=ConflictingStore(),
    )

    with pytest.raises(
        RepositoryEvidenceConflictError,
        match="Forced revision conflict",
    ):
        coordinator.sync_repository(
            repository_url=REPOSITORY_URL,
            observed_at=OBSERVED_AT,
        )
