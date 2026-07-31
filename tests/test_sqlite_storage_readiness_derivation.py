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


def _in_memory_snapshot(
    *,
    schema_version=CURRENT_SQLITE_SCHEMA_VERSION,
    user_version=CURRENT_SQLITE_SCHEMA_VERSION,
    integrity_messages=("ok",),
    foreign_key_violations=(),
    receipts=(),
    unparseable_receipt_rows=(),
    required_tables_present=True,
    receipts_read_error=None,
):
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteTablePresence,
        SQLiteTrustedStoreRawSnapshot,
    )

    return SQLiteTrustedStoreRawSnapshot(
        required_tables=(
            SQLiteTablePresence(
                table_name=(
                    "execution_evidence_"
                    "schema_migrations"
                ),
                present=required_tables_present,
            ),
            SQLiteTablePresence(
                table_name=(
                    "execution_evidence_"
                    "import_receipts"
                ),
                present=required_tables_present,
            ),
        ),
        schema_migration_version=(
            schema_version
            if required_tables_present
            else None
        ),
        schema_migration_version_read_error=None,
        user_version=user_version,
        user_version_read_error=None,
        data_version=1,
        data_version_read_error=None,
        integrity_messages=integrity_messages,
        integrity_read_error=None,
        foreign_key_violations=(
            foreign_key_violations
        ),
        foreign_key_read_error=None,
        receipt_row_count=(
            len(receipts)
            + len(unparseable_receipt_rows)
            if (
                required_tables_present
                and receipts_read_error is None
            )
            else None
        ),
        receipts=receipts,
        unparseable_receipt_rows=(
            unparseable_receipt_rows
        ),
        receipts_read_error=receipts_read_error,
    )


def test_derivation_accepts_entirely_in_memory_snapshot():
    snapshot = _in_memory_snapshot()

    readiness = derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.backend == "sqlite"
    assert readiness.status == "misconfigured"
    assert readiness.migration_receipt_count == 0
    assert readiness.checks == {
        "database_exists": True,
        "database_readable": True,
        "schema_current": True,
        "integrity_valid": True,
        "foreign_keys_valid": True,
        "migration_receipt_present": False,
        "trusted_receipt_present": False,
        "trusted_receipt_chain_valid": False,
        "trusted_receipt_compatible": False,
    }
    assert readiness.errors == [
        "SQLite database has no trusted-store "
        "initialization or migration receipt."
    ]


@pytest.mark.parametrize(
    (
        "snapshot",
        "expected_errors",
    ),
    (
        (
            _in_memory_snapshot(
                schema_version=(
                    CURRENT_SQLITE_SCHEMA_VERSION - 1
                ),
                integrity_messages=(
                    "database disk image is malformed",
                ),
            ),
            [
                "SQLite execution evidence schema "
                "version is not current.",
                "SQLite integrity validation failed.",
            ],
        ),
        (
            _in_memory_snapshot(
                schema_version=(
                    CURRENT_SQLITE_SCHEMA_VERSION - 1
                ),
                foreign_key_violations=(
                    __import__(
                        "execution_evidence."
                        "sqlite_trusted_store_snapshot",
                        fromlist=[
                            "SQLiteForeignKeyViolation"
                        ],
                    ).SQLiteForeignKeyViolation(
                        table="child",
                        rowid=1,
                        parent="parent",
                        foreign_key_index=0,
                    ),
                ),
            ),
            [
                "SQLite execution evidence schema "
                "version is not current.",
                "SQLite foreign-key validation failed.",
            ],
        ),
        (
            _in_memory_snapshot(
                integrity_messages=(
                    "database disk image is malformed",
                ),
                foreign_key_violations=(
                    __import__(
                        "execution_evidence."
                        "sqlite_trusted_store_snapshot",
                        fromlist=[
                            "SQLiteForeignKeyViolation"
                        ],
                    ).SQLiteForeignKeyViolation(
                        table="child",
                        rowid=1,
                        parent="parent",
                        foreign_key_index=0,
                    ),
                ),
            ),
            [
                "SQLite integrity validation failed.",
                "SQLite foreign-key validation failed.",
            ],
        ),
    ),
)
def test_compound_failure_precedence_is_characterized(
    snapshot,
    expected_errors,
):
    readiness = derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.status == "misconfigured"
    assert readiness.errors == expected_errors
    assert (
        readiness.trusted_receipt_chain_valid
        is None
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        is None
    )


@pytest.mark.parametrize(
    "snapshot",
    (
        _in_memory_snapshot(
            schema_version=(
                CURRENT_SQLITE_SCHEMA_VERSION - 1
            ),
        ),
        _in_memory_snapshot(
            integrity_messages=(
                "database disk image is malformed",
            ),
        ),
        _in_memory_snapshot(
            foreign_key_violations=(
                __import__(
                    "execution_evidence."
                    "sqlite_trusted_store_snapshot",
                    fromlist=[
                        "SQLiteForeignKeyViolation"
                    ],
                ).SQLiteForeignKeyViolation(
                    table="child",
                    rowid=1,
                    parent="parent",
                    foreign_key_index=0,
                ),
            ),
        ),
    ),
)
def test_chain_validation_is_skipped_for_structural_failures(
    snapshot,
    monkeypatch,
):
    import execution_evidence.storage_readiness as module

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Receipt-chain validation must be skipped."
        )

    monkeypatch.setattr(
        module,
        "validate_trusted_receipt_chain",
        fail_if_called,
    )

    readiness = module.derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.trusted_receipt_chain_valid
        is None
    )


def test_chain_validation_is_skipped_for_malformed_receipts(
    monkeypatch,
):
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteUnparseableTrustedReceiptRow,
    )
    import execution_evidence.storage_readiness as module

    snapshot = _in_memory_snapshot(
        unparseable_receipt_rows=(
            SQLiteUnparseableTrustedReceiptRow(
                receipt_rowid=7,
                snapshot_row_index=0,
                receipt_id="broken",
                error_type="ValidationError",
            ),
        ),
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Receipt-chain validation must be skipped."
        )

    monkeypatch.setattr(
        module,
        "validate_trusted_receipt_chain",
        fail_if_called,
    )

    readiness = module.derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.storage_failure_code
        == "receipt_parse_failure"
    )
    assert (
        readiness.trusted_receipt_chain_valid
        is None
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        is None
    )
    assert readiness.trusted_receipt_chain_tip is None
    assert (
        readiness.trusted_receipt_chain_length
        is None
    )


# storage_readiness_contract_hardening


def test_receipt_parse_failure_is_pre_chain_primary_diagnosis():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteUnparseableTrustedReceiptRow,
    )

    snapshot = _in_memory_snapshot(
        unparseable_receipt_rows=(
            SQLiteUnparseableTrustedReceiptRow(
                receipt_rowid=9,
                snapshot_row_index=0,
                receipt_id="malformed",
                error_type="ValidationError",
            ),
        ),
    )

    readiness = derive_sqlite_storage_readiness(
        snapshot
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.storage_failure_code
        == "receipt_parse_failure"
    )
    assert (
        readiness.trusted_receipt_chain_valid
        is None
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        is None
    )


@pytest.mark.parametrize(
    (
        "snapshot",
        "expected_failure_code",
    ),
    (
        (
            _in_memory_snapshot(
                schema_version=(
                    CURRENT_SQLITE_SCHEMA_VERSION - 1
                ),
                integrity_messages=(
                    "database disk image is malformed",
                ),
            ),
            "schema_version_mismatch",
        ),
        (
            _in_memory_snapshot(
                integrity_messages=(
                    "database disk image is malformed",
                ),
                foreign_key_violations=(
                    __import__(
                        "execution_evidence."
                        "sqlite_trusted_store_snapshot",
                        fromlist=[
                            "SQLiteForeignKeyViolation"
                        ],
                    ).SQLiteForeignKeyViolation(
                        table="child",
                        rowid=1,
                        parent="parent",
                        foreign_key_index=0,
                    ),
                ),
            ),
            "integrity_validation_failed",
        ),
        (
            _in_memory_snapshot(
                schema_version=(
                    CURRENT_SQLITE_SCHEMA_VERSION - 1
                ),
                integrity_messages=(
                    "database disk image is malformed",
                ),
                foreign_key_violations=(
                    __import__(
                        "execution_evidence."
                        "sqlite_trusted_store_snapshot",
                        fromlist=[
                            "SQLiteForeignKeyViolation"
                        ],
                    ).SQLiteForeignKeyViolation(
                        table="child",
                        rowid=1,
                        parent="parent",
                        foreign_key_index=0,
                    ),
                ),
            ),
            "schema_version_mismatch",
        ),
    ),
)
def test_storage_failure_precedence_is_explicit(
    snapshot,
    expected_failure_code,
):
    readiness = derive_sqlite_storage_readiness(
        snapshot
    )

    assert (
        readiness.storage_failure_code
        == expected_failure_code
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        is None
    )


def test_all_sqlite_derivation_failure_codes_are_emitted():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteForeignKeyViolation,
        SQLiteSnapshotReadError,
        SQLiteUnparseableTrustedReceiptRow,
    )

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

    conflicting_root = root.model_copy(
        update={
            "receipt_id": "pending",
            "lineage_epoch": 2,
        }
    )
    conflicting_root = conflicting_root.model_copy(
        update={
            "receipt_id": (
                calculate_migration_receipt_id(
                    conflicting_root
                )
            ),
        }
    )

    cases = {
        "trusted_store_tables_missing": (
            _in_memory_snapshot(
                required_tables_present=False,
            )
        ),
        "schema_version_mismatch": (
            _in_memory_snapshot(
                schema_version=(
                    CURRENT_SQLITE_SCHEMA_VERSION - 1
                ),
            )
        ),
        "integrity_validation_failed": (
            _in_memory_snapshot(
                integrity_messages=(
                    "database disk image is malformed",
                ),
            )
        ),
        "foreign_key_validation_failed": (
            _in_memory_snapshot(
                foreign_key_violations=(
                    SQLiteForeignKeyViolation(
                        table="child",
                        rowid=1,
                        parent="parent",
                        foreign_key_index=0,
                    ),
                ),
            )
        ),
        "receipts_unreadable": (
            _in_memory_snapshot(
                receipts_read_error=(
                    SQLiteSnapshotReadError(
                        operation="read_receipts",
                        error_type="OperationalError",
                        message="receipt query failed",
                    )
                ),
            )
        ),
        "receipt_parse_failure": (
            _in_memory_snapshot(
                unparseable_receipt_rows=(
                    SQLiteUnparseableTrustedReceiptRow(
                        receipt_rowid=7,
                        snapshot_row_index=0,
                        receipt_id="broken",
                        error_type="ValidationError",
                    ),
                ),
            )
        ),
        "trusted_receipts_missing": (
            _in_memory_snapshot()
        ),
        "trusted_receipt_chain_invalid": (
            _in_memory_snapshot(
                receipts=(
                    root,
                    conflicting_root,
                ),
            )
        ),
    }

    emitted = {
        expected: (
            derive_sqlite_storage_readiness(
                snapshot
            ).storage_failure_code
        )
        for expected, snapshot in cases.items()
    }

    assert emitted == {
        expected: expected
        for expected in cases
    }
