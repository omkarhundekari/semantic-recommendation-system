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
    assess_sqlite_database_readiness,
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


def test_initialized_sqlite_without_receipt_is_degraded(
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

    assert readiness.status == "degraded"
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


def test_sqlite_with_receipt_is_ready(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    SQLiteRepositoryEvidenceStore(
        database_path
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
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "receipt-1",
                "json",
                "repositories.json",
                "abc123",
                1,
                1,
                0,
                0,
                0,
                '{"verified":true}',
                "2026-07-13T12:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()

    readiness = (
        assess_sqlite_database_readiness(
            database_path
        )
    )

    assert readiness.status == "ready"
    assert readiness.migration_receipt_count == 1


def test_sqlite_schema_mismatch_is_misconfigured(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
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
