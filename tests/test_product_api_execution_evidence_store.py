from datetime import datetime
from pathlib import Path

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from execution_evidence.models import (
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    StoredRepositoryEvidence,
)
from product_api import (
    DEFAULT_EXECUTION_EVIDENCE_STORE_PATH,
    EXECUTION_EVIDENCE_STORE_PATH_ENV,
    build_execution_evidence_store,
    get_execution_evidence_coordinator,
    get_execution_evidence_store,
)


SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)


def _record() -> StoredRepositoryEvidence:
    return StoredRepositoryEvidence(
        repository=REFERENCE,
        sync_state=RepositorySyncState(
            repository_key=REFERENCE.repository_key,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REFERENCE.repository_key,
        ),
        saved_at=SAVED_AT,
    )


def test_store_factory_uses_explicit_path(
    tmp_path: Path,
):
    store_path = tmp_path / "explicit.json"

    store = build_execution_evidence_store(
        str(store_path)
    )

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert store.path == store_path


def test_store_factory_uses_environment_path(
    tmp_path: Path,
    monkeypatch,
):
    store_path = tmp_path / "configured.json"

    monkeypatch.setenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        str(store_path),
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert store.path == store_path


def test_store_factory_uses_default_path(
    monkeypatch,
):
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert (
        store.path
        == DEFAULT_EXECUTION_EVIDENCE_STORE_PATH
    )


def test_factory_created_stores_recover_saved_records(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"

    first_store = build_execution_evidence_store(
        str(store_path)
    )
    saved = first_store.save(_record())

    restarted_store = build_execution_evidence_store(
        str(store_path)
    )
    loaded = restarted_store.load(
        REFERENCE.repository_key
    )

    assert loaded == saved
    assert loaded is not saved


def test_api_coordinator_uses_configured_store_singleton():
    coordinator = get_execution_evidence_coordinator()

    assert (
        coordinator._store
        is get_execution_evidence_store()
    )
    assert isinstance(
        coordinator._store,
        JsonRepositoryEvidenceStore,
    )
