from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import pytest

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
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
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)


StoreFactory = Callable[[], RepositoryEvidenceStore]

SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

SECOND_REFERENCE = parse_github_repository_url(
    "https://github.com/example/another-repository"
)

REPOSITORY_KEY = REFERENCE.repository_key


@pytest.fixture(
    params=[
        "in-memory",
        "json",
    ],
)
def store_factory(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> StoreFactory:
    if request.param == "in-memory":
        return InMemoryRepositoryEvidenceStore

    store_path = tmp_path / "repositories.json"

    return lambda: JsonRepositoryEvidenceStore(
        store_path
    )


def _evidence(
    external_id: str = "abc123",
) -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id=external_id,
        title="Persist execution evidence",
        url=(
            f"{REFERENCE.canonical_url}/commit/"
            f"{external_id}"
        ),
        occurred_at=SAVED_AT,
        first_seen_at=SAVED_AT,
        last_seen_at=SAVED_AT,
    )


def _record(
    *,
    reference=REFERENCE,
    evidence: Optional[
        List[ExecutionEvidenceItem]
    ] = None,
) -> StoredRepositoryEvidence:
    repository_key = reference.repository_key

    return StoredRepositoryEvidence(
        repository=reference,
        evidence=(
            [_evidence()]
            if evidence is None
            and reference == REFERENCE
            else evidence or []
        ),
        sync_state=RepositorySyncState(
            repository_key=repository_key,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=repository_key,
        ),
        saved_at=SAVED_AT,
    )


def test_store_returns_none_for_missing_repository(
    store_factory: StoreFactory,
):
    store = store_factory()

    assert store.load(REPOSITORY_KEY) is None


def test_store_saves_and_loads_repository_aggregate(
    store_factory: StoreFactory,
):
    store = store_factory()

    saved = store.save(_record())
    loaded = store.load(REPOSITORY_KEY)

    assert saved.revision == 0
    assert loaded == saved
    assert loaded is not saved


def test_store_returns_defensive_copies(
    store_factory: StoreFactory,
):
    store = store_factory()
    saved = store.save(_record())

    loaded = store.load(REPOSITORY_KEY)
    assert loaded is not None

    loaded.evidence.clear()

    reloaded = store.load(REPOSITORY_KEY)

    assert reloaded is not None
    assert len(reloaded.evidence) == 1
    assert len(saved.evidence) == 1


def test_store_increments_revision_on_replacement(
    store_factory: StoreFactory,
):
    store = store_factory()
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
        },
        deep=True,
    )

    second = store.save(
        replacement,
        expected_revision=first.revision,
    )

    assert second.revision == 1
    assert len(second.evidence) == 2
    assert store.load(REPOSITORY_KEY) == second


def test_store_rejects_stale_revision_without_mutation(
    store_factory: StoreFactory,
):
    store = store_factory()
    first = store.save(_record())

    current = store.save(
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

    assert store.load(REPOSITORY_KEY) == current


def test_store_deletes_repository_record(
    store_factory: StoreFactory,
):
    store = store_factory()
    store.save(_record())

    assert store.delete(REPOSITORY_KEY) is True
    assert store.load(REPOSITORY_KEY) is None
    assert store.delete(REPOSITORY_KEY) is False


def test_store_lists_repository_keys_in_stable_order(
    store_factory: StoreFactory,
):
    store = store_factory()

    store.save(_record())
    store.save(
        _record(
            reference=SECOND_REFERENCE,
            evidence=[],
        )
    )

    assert store.list_repository_keys() == sorted(
        [
            REPOSITORY_KEY,
            SECOND_REFERENCE.repository_key,
        ]
    )


def test_store_updates_one_repository_without_mutating_another(
    store_factory: StoreFactory,
):
    store = store_factory()

    first_saved = store.save(_record())
    second_saved = store.save(
        _record(
            reference=SECOND_REFERENCE,
            evidence=[],
        )
    )

    updated_first = store.save(
        first_saved.model_copy(
            update={
                "evidence": [
                    _evidence("abc123"),
                    _evidence("def456"),
                ],
            },
            deep=True,
        ),
        expected_revision=first_saved.revision,
    )

    assert updated_first.revision == 1
    assert (
        store.load(
            SECOND_REFERENCE.repository_key
        )
        == second_saved
    )
