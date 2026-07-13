import json
from datetime import datetime
from pathlib import Path

import pytest

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
    RepositoryEvidenceStoreError,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
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
        title="Persist execution evidence",
        url=(
            f"{REFERENCE.canonical_url}/commit/"
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


def test_json_store_persists_across_instances(
    tmp_path: Path,
):
    store_path = (
        tmp_path
        / "execution-evidence"
        / "repositories.json"
    )

    first_store = JsonRepositoryEvidenceStore(
        store_path
    )
    saved = first_store.save(_record())

    second_store = JsonRepositoryEvidenceStore(
        store_path
    )
    loaded = second_store.load(REPOSITORY_KEY)

    assert saved.revision == 0
    assert loaded == saved
    assert loaded is not saved


def test_json_store_returns_defensive_copies(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )
    saved = store.save(_record())

    loaded = store.load(REPOSITORY_KEY)
    assert loaded is not None

    loaded.evidence.clear()

    reloaded = store.load(REPOSITORY_KEY)

    assert reloaded is not None
    assert len(reloaded.evidence) == 1
    assert len(saved.evidence) == 1


def test_json_store_increments_revision(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )

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


def test_json_store_rejects_stale_revision(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )
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


def test_json_store_deletes_persisted_record(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store = JsonRepositoryEvidenceStore(store_path)
    store.save(_record())

    assert store.delete(REPOSITORY_KEY) is True

    restarted_store = JsonRepositoryEvidenceStore(
        store_path
    )

    assert (
        restarted_store.load(REPOSITORY_KEY)
        is None
    )
    assert (
        restarted_store.delete(REPOSITORY_KEY)
        is False
    )


def test_json_store_lists_keys_in_stable_order(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )

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


def test_json_store_creates_parent_directory(
    tmp_path: Path,
):
    store_path = (
        tmp_path
        / "nested"
        / "execution"
        / "repositories.json"
    )

    store = JsonRepositoryEvidenceStore(store_path)
    store.save(_record())

    assert store_path.exists()


def test_json_store_rejects_invalid_json(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    store = JsonRepositoryEvidenceStore(store_path)

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="invalid JSON",
    ):
        store.list_repository_keys()


def test_json_store_rejects_invalid_schema(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": {
                    REPOSITORY_KEY: {
                        "schema_version": 1,
                        "repository": {
                            "provider": "github",
                            "owner": "owner",
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = JsonRepositoryEvidenceStore(store_path)

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="schema validation",
    ):
        store.load(REPOSITORY_KEY)


def test_json_store_rejects_wrong_record_key(
    tmp_path: Path,
):
    record_payload = _record().model_dump(
        mode="json"
    )

    store_path = tmp_path / "repositories.json"
    store_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": {
                    "github:wrong/repository": (
                        record_payload
                    ),
                },
            }
        ),
        encoding="utf-8",
    )

    store = JsonRepositoryEvidenceStore(store_path)

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="schema validation",
    ):
        store.list_repository_keys()


def test_json_store_replaces_file_atomically(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store = JsonRepositoryEvidenceStore(store_path)

    first = store.save(_record())
    original_payload = store_path.read_text(
        encoding="utf-8"
    )

    second = store.save(
        first,
        expected_revision=first.revision,
    )
    replaced_payload = store_path.read_text(
        encoding="utf-8"
    )

    assert second.revision == 1
    assert replaced_payload != original_payload
    assert not list(
        tmp_path.glob(
            ".repositories.json.*.tmp"
        )
    )
