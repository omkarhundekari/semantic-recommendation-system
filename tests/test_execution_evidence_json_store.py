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


def _record() -> StoredRepositoryEvidence:
    evidence = ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id="abc123",
        title="Persist execution evidence",
        url=(
            f"{REFERENCE.canonical_url}/commit/"
            "abc123"
        ),
        occurred_at=SAVED_AT,
        first_seen_at=SAVED_AT,
        last_seen_at=SAVED_AT,
    )

    return StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[evidence],
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

    saved = JsonRepositoryEvidenceStore(
        store_path
    ).save(_record())

    loaded = JsonRepositoryEvidenceStore(
        store_path
    ).load(REPOSITORY_KEY)

    assert loaded == saved
    assert loaded is not saved


def test_json_store_creates_parent_directory(
    tmp_path: Path,
):
    store_path = (
        tmp_path
        / "nested"
        / "execution"
        / "repositories.json"
    )

    JsonRepositoryEvidenceStore(
        store_path
    ).save(_record())

    assert store_path.exists()


def test_json_store_rejects_invalid_json(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="invalid JSON",
    ):
        JsonRepositoryEvidenceStore(
            store_path
        ).list_repository_keys()


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

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="schema validation",
    ):
        JsonRepositoryEvidenceStore(
            store_path
        ).load(REPOSITORY_KEY)


def test_json_store_rejects_wrong_record_key(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "records": {
                    "github:wrong/repository": (
                        _record().model_dump(
                            mode="json"
                        )
                    ),
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryEvidenceStoreError,
        match="schema validation",
    ):
        JsonRepositoryEvidenceStore(
            store_path
        ).list_repository_keys()


def test_json_store_replaces_file_atomically(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    store = JsonRepositoryEvidenceStore(
        store_path
    )

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
