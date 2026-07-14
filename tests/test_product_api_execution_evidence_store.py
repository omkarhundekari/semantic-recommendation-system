from datetime import datetime
from pathlib import Path

import pytest

import product_api

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
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)
from product_api import (
    DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND,
    DEFAULT_EXECUTION_EVIDENCE_STORE_PATH,
    DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH,
    EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
    EXECUTION_EVIDENCE_STORE_PATH_ENV,
    build_execution_evidence_storage_runtime,
    build_execution_evidence_store,
    get_execution_evidence_coordinator,
    get_execution_evidence_storage_runtime,
    get_execution_evidence_store,
    get_roadmap_snapshot_registry,
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
    tmp_path: Path,
    monkeypatch,
):
    json_path = tmp_path / "repositories.json"
    sqlite_path = tmp_path / "missing.db"

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_EXECUTION_EVIDENCE_STORE_PATH",
        json_path,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        sqlite_path,
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == sqlite_path
    assert sqlite_path.is_file()


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


def test_store_factory_defaults_to_auto_backend(
    tmp_path: Path,
    monkeypatch,
):
    json_path = tmp_path / "repositories.json"
    sqlite_path = tmp_path / "missing.db"

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_EXECUTION_EVIDENCE_STORE_PATH",
        json_path,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        sqlite_path,
    )

    store = build_execution_evidence_store()

    assert (
        DEFAULT_EXECUTION_EVIDENCE_STORE_BACKEND
        == "auto"
    )
    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == sqlite_path


def test_store_factory_uses_sqlite_backend_explicitly(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
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
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
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
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "missing.db"

    monkeypatch.setenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        "sqlite",
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        database_path,
    )

    with pytest.raises(
        ValueError,
        match="existing promoted database",
    ) as error:
        build_execution_evidence_store()

    assert str(database_path) in str(error.value)


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
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
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

    assert version == (
        CURRENT_SQLITE_SCHEMA_VERSION - 1
    )


def test_auto_backend_uses_valid_canonical_sqlite_database(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        database_path,
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == database_path


def test_auto_backend_rejects_invalid_canonical_sqlite_database(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    database_path.write_bytes(b"not-a-sqlite-database")

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        database_path,
    )

    with pytest.raises(
        ValueError,
        match="failed readiness validation",
    ):
        build_execution_evidence_store()


def test_auto_backend_infers_json_from_explicit_path(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"

    store = build_execution_evidence_store(
        str(store_path),
        backend="auto",
    )

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert store.path == store_path


def test_auto_backend_infers_sqlite_from_explicit_path(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    store = build_execution_evidence_store(
        str(database_path),
        backend="auto",
    )

    assert isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    )
    assert store.path == database_path


def test_auto_backend_rejects_unknown_path_extension(
    tmp_path: Path,
):
    with pytest.raises(
        ValueError,
        match=r"requires a \.json or \.db path",
    ):
        build_execution_evidence_store(
            str(tmp_path / "evidence.data"),
            backend="auto",
        )



def test_auto_backend_preserves_existing_legacy_json_store(
    tmp_path: Path,
    monkeypatch,
):
    json_path = tmp_path / "repositories.json"
    sqlite_path = tmp_path / "solvyn.db"

    JsonRepositoryEvidenceStore(
        json_path
    ).restore([])

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_EXECUTION_EVIDENCE_STORE_PATH",
        json_path,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        sqlite_path,
    )

    store = build_execution_evidence_store()

    assert isinstance(
        store,
        JsonRepositoryEvidenceStore,
    )
    assert store.path == json_path
    assert not sqlite_path.exists()


def test_auto_backend_rejects_schema_only_canonical_database(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    json_path = tmp_path / "repositories.json"

    SQLiteRepositoryEvidenceStore(
        database_path
    )
    JsonRepositoryEvidenceStore(
        json_path
    ).restore([])

    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_BACKEND_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        EXECUTION_EVIDENCE_STORE_PATH_ENV,
        raising=False,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_EXECUTION_EVIDENCE_STORE_PATH",
        json_path,
    )
    monkeypatch.setattr(
        product_api,
        "DEFAULT_SQLITE_EXECUTION_EVIDENCE_STORE_PATH",
        database_path,
    )

    with pytest.raises(
        ValueError,
        match="failed readiness validation",
    ):
        build_execution_evidence_store()



def test_sqlite_runtime_exposes_shared_roadmap_registry(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    runtime = (
        build_execution_evidence_storage_runtime(
            str(database_path),
            backend="sqlite",
        )
    )

    assert (
        runtime.roadmap_registry_status
        == "ready"
    )
    assert runtime.remediation is None
    assert runtime.trusted_sqlite_service is not None
    assert runtime.roadmap_registry is not None
    assert (
        runtime.evidence_store.path
        == database_path
    )
    assert (
        runtime.roadmap_registry.path
        == database_path
    )


def test_json_runtime_reports_roadmap_registry_unavailable(
    tmp_path: Path,
):
    json_path = tmp_path / "repositories.json"

    runtime = (
        build_execution_evidence_storage_runtime(
            str(json_path),
            backend="json",
        )
    )

    assert isinstance(
        runtime.evidence_store,
        JsonRepositoryEvidenceStore,
    )
    assert runtime.trusted_sqlite_service is None
    assert runtime.roadmap_registry is None
    assert (
        runtime.roadmap_registry_status
        == "unavailable_legacy_store"
    )
    assert "Migrate" in runtime.remediation


def test_runtime_singleton_drives_both_dependencies():
    runtime = (
        get_execution_evidence_storage_runtime()
    )

    assert (
        get_execution_evidence_store()
        is runtime.evidence_store
    )
    assert (
        get_roadmap_snapshot_registry()
        is runtime.roadmap_registry
    )
