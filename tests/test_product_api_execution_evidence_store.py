from datetime import datetime
from pathlib import Path

import pytest

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
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.store import (
    StoredRepositoryEvidence,
)
from product_api import (
    DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND,
    DEFAULT_EXECUTION_EVIDENCE_STORE_PATH,
    DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH,
    EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
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


def test_store_factory_defaults_to_json_backend(
    monkeypatch,
):
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )

    store = build_execution_evidence_store()

    assert (
        DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND
        == "json"
    )
    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )


def test_store_factory_uses_sqlite_backend_explicitly(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    SQLiteRepositoryEvidenceStore(
        database_path
    )

    store = build_execution_evidence_store(
        str(database_path),
        backend="sqlite",
    )

    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == database_path


def test_store_factory_uses_sqlite_environment_configuration(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "configured.db"
    SQLiteRepositoryEvidenceStore(
        database_path
    )

    monkeypatch.setenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        "sqlite",
    )
    monkeypatch.setenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        str(database_path),
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == database_path


def test_sqlite_backend_uses_sqlite_default_path(
    monkeypatch,
):
    monkeypatch.setenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        "sqlite",
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )

    with pytest.raises(
        ValueError,
        match="existing promoted database",
    ) as error:
        build_execution_evidence_store()

    assert (
        str(
            DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH
        )
        in str(error.value)
    )


def test_store_factory_rejects_unknown_backend():
    with pytest.raises(
        ValueError,
        match="Unsupported execution evidence",
    ):
        build_execution_evidence_store(
            backend="postgres",
        )


@pytest.mark.parametrize(
    ("backend", "filename", "message"),
    [
        (
            "json",
            "repositories.db",
            r"requires a \.json path",
        ),
        (
            "sqlite",
            "solvyn.json",
            r"requires a \.db path",
        ),
    ],
)
def test_store_factory_rejects_backend_path_mismatch(
    tmp_path: Path,
    backend: str,
    filename: str,
    message: str,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        build_execution_evidence_store(
            str(tmp_path / filename),
            backend=backend,
        )


def test_sqlite_backend_rejects_missing_database(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"

    with pytest.raises(
        ValueError,
        match="existing promoted database",
    ):
        build_execution_evidence_store(
            str(database_path),
            backend="sqlite",
        )

    assert not database_path.exists()


def test_explicit_path_remains_json_compatible_when_backend_omitted(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )

    store_path = tmp_path / "compatible.json"

    store = build_execution_evidence_store(
        str(store_path)
    )

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert store.path == store_path


def test_runtime_sqlite_factory_does_not_apply_schema_migrations(
    tmp_path: Path,
):
    import sqlite3

    database_path = tmp_path / "outdated.db"
    SQLiteRepositoryEvidenceStore(
        database_path
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        connection.execute(
            """
            DELETE FROM
                execution_evidence_schema_migrations
            WHERE version = (
                SELECT MAX(version)
                FROM
                    execution_evidence_schema_migrations
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        ValueError,
        match="failed readiness validation",
    ):
        build_execution_evidence_store(
            str(database_path),
            backend="sqlite",
        )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        version = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
            FROM
                execution_evidence_schema_migrations
            """
        ).fetchone()[0]
    finally:
        connection.close()

    assert version == 2
