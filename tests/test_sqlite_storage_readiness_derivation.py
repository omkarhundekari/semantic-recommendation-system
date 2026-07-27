from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.sqlite_trusted_store_snapshot import (
    capture_sqlite_trusted_store_snapshot,
)
from execution_evidence.storage_readiness import (
    assess_sqlite_database_readiness,
    derive_sqlite_storage_readiness,
)
from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_V2_VERSION,
    calculate_migration_receipt_id,
    persist_migration_receipt,
)
from execution_evidence.trusted_store import (
    build_fresh_init_receipt,
    initialize_fresh_trusted_store,
)


CREATED_AT = "2026-07-13T12:00:00+00:00"


def _derive_from_database(
    database_path: Path,
):
    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )
        return derive_sqlite_storage_readiness(
            snapshot
        )
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def _assert_differential_equivalence(
    database_path: Path,
):
    old_readiness = (
        assess_sqlite_database_readiness(
            database_path
        )
    )
    new_readiness = _derive_from_database(
        database_path
    )

    assert new_readiness == old_readiness
    assert (
        new_readiness.model_dump(mode="json")
        == old_readiness.model_dump(mode="json")
    )


def test_derivation_matches_old_builder_for_empty_receipts(
    tmp_path: Path,
):
    database_path = tmp_path / "empty.db"
    SQLiteRepositoryEvidenceStore(database_path)

    _assert_differential_equivalence(
        database_path
    )


def test_derivation_matches_old_builder_for_legacy_receipt(
    tmp_path: Path,
):
    database_path = tmp_path / "legacy.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    _assert_differential_equivalence(
        database_path
    )


def test_derivation_matches_old_builder_for_valid_v2_chain(
    tmp_path: Path,
):
    database_path = tmp_path / "v2.db"
    SQLiteRepositoryEvidenceStore(database_path)

    legacy = build_fresh_init_receipt(
        created_at=CREATED_AT,
    )
    root = legacy.model_copy(
        update={
            "receipt_version": (
                MIGRATION_RECEIPT_V2_VERSION
            ),
            "receipt_id": "pending",
            "receipt_kind": "root",
            "predecessor_receipt_id": None,
            "schema_version_from": None,
            "schema_version_to": (
                CURRENT_SQLITE_SCHEMA_VERSION
            ),
            "lineage_epoch": 1,
        }
    )
    root = root.model_copy(
        update={
            "receipt_id": (
                calculate_migration_receipt_id(
                    root
                )
            ),
        }
    )

    persist_migration_receipt(
        database_path=database_path,
        receipt=root,
    )

    _assert_differential_equivalence(
        database_path
    )


def test_derivation_matches_old_builder_for_malformed_receipt(
    tmp_path: Path,
):
    database_path = tmp_path / "malformed.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        connection.execute(
            """
            UPDATE execution_evidence_import_receipts
            SET repository_count = -1
            """
        )
        connection.commit()
    finally:
        connection.close()

    _assert_differential_equivalence(
        database_path
    )


def test_derivation_matches_old_builder_for_schema_mismatch(
    tmp_path: Path,
):
    database_path = tmp_path / "schema.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
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

    _assert_differential_equivalence(
        database_path
    )


def test_derivation_is_in_memory_and_requires_no_connection(
    tmp_path: Path,
):
    database_path = tmp_path / "memory-only.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()

    readiness = derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.backend == "sqlite"
    assert readiness.status == "degraded"


def test_derivation_does_not_deserialize_receipts():
    import execution_evidence.storage_readiness as module

    assert (
        "deserialize_repository_evidence_migration_receipt"
        not in derive_sqlite_storage_readiness.__code__.co_names
    )

    assert (
        "ValidationError"
        not in derive_sqlite_storage_readiness.__code__.co_names
    )

    assert module.sqlite3 is sqlite3


def test_connection_readiness_uses_snapshot_derivation(
    tmp_path: Path,
    monkeypatch,
):
    import execution_evidence.storage_readiness as module

    database_path = tmp_path / "redirect.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    calls = {
        "capture": 0,
        "derive": 0,
    }

    real_capture = (
        module.capture_sqlite_trusted_store_snapshot
    )
    real_derive = (
        module.derive_sqlite_storage_readiness
    )

    def recording_capture(connection):
        calls["capture"] += 1
        return real_capture(connection)

    def recording_derive(snapshot):
        calls["derive"] += 1
        return real_derive(snapshot)

    monkeypatch.setattr(
        module,
        "capture_sqlite_trusted_store_snapshot",
        recording_capture,
    )
    monkeypatch.setattr(
        module,
        "derive_sqlite_storage_readiness",
        recording_derive,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")

        readiness = (
            module.assess_sqlite_connection_readiness(
                connection
            )
        )

        assert readiness.status == "degraded"
        assert calls == {
            "capture": 1,
            "derive": 1,
        }
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_connection_readiness_preserves_missing_table_error():
    from execution_evidence.storage_readiness import (
        assess_sqlite_connection_readiness,
    )

    connection = sqlite3.connect(
        ":memory:",
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")

        with pytest.raises(sqlite3.Error):
            assess_sqlite_connection_readiness(
                connection
            )

        assert connection.in_transaction is True
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_readiness_module_has_no_duplicate_receipt_parse_path():
    import inspect
    import execution_evidence.storage_readiness as module

    source = inspect.getsource(module)

    assert "_build_sqlite_readiness" not in source
    assert (
        "load_trusted_receipt_rows_from_connection"
        not in source
    )
    assert (
        "deserialize_repository_evidence_migration_receipt"
        not in source
    )
    assert "ValidationError" not in source
