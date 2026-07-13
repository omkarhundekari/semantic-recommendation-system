from datetime import datetime

import pytest
from pydantic import ValidationError

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    InMemoryRepositoryEvidenceStore,
    RepositoryEvidenceConflictError,
    StoredRepositoryEvidence,
)


SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

REPOSITORY_KEY = REFERENCE.repository_key


def _evidence(
    external_id: str = "abc123",
) -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id=external_id,
        title="Add repository evidence store",
        url=(
            "https://github.com/omkarhundekari/"
            "semantic-recommendation-system/commit/"
            f"{external_id}"
        ),
        occurred_at=SAVED_AT,
        first_seen_at=SAVED_AT,
        last_seen_at=SAVED_AT,
    )


def _record() -> StoredRepositoryEvidence:
    return StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[_evidence()],
        sync_state=RepositorySyncState(
            repository_key=REPOSITORY_KEY,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
        ),
        saved_at=SAVED_AT,
    )


def test_store_saves_and_loads_repository_aggregate():
    store = InMemoryRepositoryEvidenceStore()

    saved = store.save(_record())
    loaded = store.load(REPOSITORY_KEY)

    assert saved.revision == 0
    assert loaded == saved
    assert loaded is not saved


def test_store_returns_defensive_copies():
    store = InMemoryRepositoryEvidenceStore()
    saved = store.save(_record())

    loaded = store.load(REPOSITORY_KEY)
    assert loaded is not None

    loaded.evidence.clear()

    reloaded = store.load(REPOSITORY_KEY)

    assert reloaded is not None
    assert len(reloaded.evidence) == 1
    assert len(saved.evidence) == 1


def test_store_increments_revision_on_replacement():
    store = InMemoryRepositoryEvidenceStore()

    first = store.save(_record())

    replacement = first.model_copy(
        update={
            "evidence": [
                _evidence("abc123"),
                _evidence("def456"),
            ],
            "saved_at": datetime.fromisoformat(
                "2026-07-13T13:00:00+00:00"
            ),
        }
    )

    second = store.save(
        replacement,
        expected_revision=first.revision,
    )

    assert second.revision == 1
    assert len(second.evidence) == 2


def test_store_rejects_stale_revision():
    store = InMemoryRepositoryEvidenceStore()
    first = store.save(_record())

    store.save(
        first,
        expected_revision=first.revision,
    )

    with pytest.raises(
        RepositoryEvidenceConflictError,
        match="revision conflict",
    ):
        store.save(
            first,
            expected_revision=first.revision,
        )


def test_store_deletes_repository_record():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())

    assert store.delete(REPOSITORY_KEY) is True
    assert store.load(REPOSITORY_KEY) is None
    assert store.delete(REPOSITORY_KEY) is False


def test_store_lists_repository_keys_in_stable_order():
    store = InMemoryRepositoryEvidenceStore()

    second_reference = parse_github_repository_url(
        "https://github.com/example/another-repository"
    )

    store.save(_record())
    store.save(
        StoredRepositoryEvidence(
            repository=second_reference,
            sync_state=RepositorySyncState(
                repository_key=(
                    second_reference.repository_key
                ),
            ),
            sync_snapshot=(
                GitHubRepositorySyncSnapshot(
                    repository_key=(
                        second_reference.repository_key
                    ),
                )
            ),
            saved_at=SAVED_AT,
        )
    )

    assert store.list_repository_keys() == sorted(
        [
            REPOSITORY_KEY,
            second_reference.repository_key,
        ]
    )


def test_record_rejects_mismatched_sync_state():
    with pytest.raises(
        ValidationError,
        match="sync state does not match",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            sync_state=RepositorySyncState(
                repository_key="github:other/repository",
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=REPOSITORY_KEY,
            ),
            saved_at=SAVED_AT,
        )


def test_record_rejects_evidence_from_other_repository():
    foreign_evidence = _evidence().model_copy(
        update={
            "repository_full_name": "other/repository",
        }
    )

    with pytest.raises(
        ValidationError,
        match="different repository",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            evidence=[foreign_evidence],
            sync_state=RepositorySyncState(
                repository_key=REPOSITORY_KEY,
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=REPOSITORY_KEY,
            ),
            saved_at=SAVED_AT,
        )
