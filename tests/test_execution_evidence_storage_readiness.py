import sqlite3
from pathlib import Path

from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_readiness import (
    assess_execution_evidence_storage_readiness,
    assess_sqlite_connection_readiness,
    assess_sqlite_database_readiness,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
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


def test_missing_json_store_is_ready_empty_storage(
    tmp_path: Path,
):
    store = JsonRepositoryEvidenceStore(
        tmp_path / "repositories.json"
    )

    readiness = (
        assess_execution_evidence_storage_readiness(
            store
        )
    )

    assert readiness.status == "ready"
    assert readiness.backend == "json"
    assert (
        readiness.writable_store_initialized
        is False
    )
    assert readiness.errors == []


def test_invalid_json_store_is_misconfigured(
    tmp_path: Path,
):
    path = tmp_path / "repositories.json"
    path.write_text(
        "{invalid",
        encoding="utf-8",
    )

    readiness = (
        assess_execution_evidence_storage_readiness(
            JsonRepositoryEvidenceStore(path)
        )
    )

    assert readiness.status == "misconfigured"
    assert readiness.backend == "json"
    assert readiness.errors


def test_initialized_sqlite_without_receipt_is_misconfigured(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    store = SQLiteRepositoryEvidenceStore(
        database_path
    )

    readiness = (
        assess_execution_evidence_storage_readiness(
            store
        )
    )

    assert readiness.status == "misconfigured"
    assert readiness.backend == "sqlite"
    assert readiness.integrity_check == "ok"
    assert (
        readiness.foreign_key_violation_count
        == 0
    )
    assert (
        readiness.checks[
            "migration_receipt_present"
        ]
        is False
    )


def test_sqlite_with_valid_legacy_receipt_is_degraded(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    readiness = (
        assess_sqlite_database_readiness(
            database_path
        )
    )

    assert readiness.status == "degraded"
    assert readiness.migration_receipt_count == 1
    assert (
        readiness.checks[
            "trusted_receipt_present"
        ]
        is True
    )
    assert (
        readiness.trusted_receipt_chain_valid
        is False
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        == "chain_not_established"
    )
    assert (
        readiness.checks[
            "trusted_receipt_compatible"
        ]
        is True
    )
    assert readiness.warnings


def test_sqlite_schema_mismatch_is_misconfigured(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
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

    readiness = (
        assess_sqlite_database_readiness(
            database_path
        )
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.checks["schema_current"]
        is False
    )


def test_sqlite_with_valid_v2_chain_is_ready(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    store = SQLiteRepositoryEvidenceStore(
        database_path
    )

    legacy = build_fresh_init_receipt(
        created_at="2026-07-13T12:00:00+00:00",
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

    readiness = (
        assess_execution_evidence_storage_readiness(
            store
        )
    )

    assert readiness.status == "ready"
    assert (
        readiness.trusted_receipt_chain_valid
        is True
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        is None
    )
    assert (
        readiness.trusted_receipt_chain_tip
        == root.receipt_id
    )
    assert (
        readiness.trusted_receipt_chain_length
        == 1
    )
    assert (
        readiness.trusted_receipt_lineage_epoch
        == 1
    )


def test_receipt_parse_failure_is_misconfigured(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
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
            UPDATE execution_evidence_import_receipts
            SET repository_count = -1
            """
        )
        connection.commit()
    finally:
        connection.close()

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.trusted_receipt_chain_valid
        is False
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        == "receipt_parse_failure"
    )
    assert readiness.errors


def test_invalid_legacy_receipt_is_misconfigured(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
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
            UPDATE execution_evidence_import_receipts
            SET receipt_id = ?
            """,
            ("0" * 64,),
        )
        connection.commit()
    finally:
        connection.close()

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.trusted_receipt_chain_failure_code
        == "id_mismatch"
    )
    assert (
        readiness.checks[
            "trusted_receipt_compatible"
        ]
        is False
    )


def test_broken_v2_chain_cannot_fall_back_to_valid_legacy(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    legacy = initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        connection.execute(
            """
            INSERT INTO execution_evidence_import_receipts (
                receipt_id,
                source_type,
                source_identifier,
                source_root_hash,
                canonicalization_version,
                report_version,
                repository_count,
                evidence_count,
                attribution_count,
                deterministic_report_json,
                created_at,
                receipt_version,
                receipt_kind,
                predecessor_receipt_id,
                schema_version_from,
                schema_version_to,
                lineage_epoch
            )
            SELECT
                ?,
                source_type,
                source_identifier,
                source_root_hash,
                canonicalization_version,
                report_version,
                repository_count,
                evidence_count,
                attribution_count,
                deterministic_report_json,
                ?,
                ?,
                'sqlite_upgrade',
                receipt_id,
                ?,
                ?,
                1
            FROM execution_evidence_import_receipts
            WHERE receipt_id = ?
            """,
            (
                "f" * 64,
                "2026-07-13T13:00:00+00:00",
                MIGRATION_RECEIPT_V2_VERSION,
                CURRENT_SQLITE_SCHEMA_VERSION - 1,
                CURRENT_SQLITE_SCHEMA_VERSION,
                legacy.receipt_id,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.status == "misconfigured"
    assert (
        readiness.trusted_receipt_chain_valid
        is False
    )
    assert (
        readiness.checks[
            "trusted_receipt_compatible"
        ]
        is False
    )
    assert (
        readiness.trusted_receipt_chain_failure_code
        != "chain_not_established"
    )


def test_connection_readiness_requires_active_transaction(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        try:
            assess_sqlite_connection_readiness(
                connection
            )
        except ValueError as error:
            assert "active caller-owned transaction" in str(
                error
            )
        else:
            raise AssertionError(
                "Readiness assessment accepted an "
                "autocommit connection."
            )
    finally:
        connection.close()


def test_connection_readiness_preserves_caller_ownership(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )
    original_row_factory = lambda cursor, row: row
    connection.row_factory = original_row_factory

    try:
        connection.execute("BEGIN")

        readiness = assess_sqlite_connection_readiness(
            connection
        )

        assert readiness.backend == "sqlite"
        assert connection.in_transaction is True
        assert (
            connection.row_factory
            is original_row_factory
        )
        assert connection.execute(
            "SELECT 1"
        ).fetchone()[0] == 1
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_connection_readiness_propagates_sqlite_errors():
    connection = sqlite3.connect(
        ":memory:",
        isolation_level=None,
    )
    original_row_factory = lambda cursor, row: row
    connection.row_factory = original_row_factory

    try:
        connection.execute("BEGIN")

        try:
            assess_sqlite_connection_readiness(
                connection
            )
        except sqlite3.Error:
            pass
        else:
            raise AssertionError(
                "Missing trusted-store tables must "
                "raise a SQLite read error."
            )

        assert connection.in_transaction is True
        assert (
            connection.row_factory
            is original_row_factory
        )
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()
