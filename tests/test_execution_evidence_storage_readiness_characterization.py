from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_readiness import (
    assess_sqlite_database_readiness,
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


def test_healthy_v2_readiness_full_contract(
    tmp_path: Path,
):
    database_path = tmp_path / "healthy.db"
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

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.model_dump(mode="json") == {
        "status": "ready",
        "backend": "sqlite",
        "writable_store_initialized": True,
        "schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "expected_schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "migration_receipt_count": 1,
        "integrity_check": "ok",
        "foreign_key_violation_count": 0,
        "trusted_receipt_chain_valid": True,
        "trusted_receipt_chain_failure_code": None,
        "trusted_receipt_chain_tip": (
            root.receipt_id
        ),
        "trusted_receipt_chain_length": 1,
        "trusted_receipt_lineage_epoch": 1,
        "checks": {
            "database_exists": True,
            "database_readable": True,
            "schema_current": True,
            "integrity_valid": True,
            "foreign_keys_valid": True,
            "migration_receipt_present": True,
            "trusted_receipt_present": True,
            "trusted_receipt_chain_valid": True,
            "trusted_receipt_compatible": True,
        },
        "warnings": [],
        "errors": [],
    }


def test_compatible_legacy_readiness_full_contract(
    tmp_path: Path,
):
    database_path = tmp_path / "legacy.db"
    receipt = initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.model_dump(mode="json") == {
        "status": "degraded",
        "backend": "sqlite",
        "writable_store_initialized": True,
        "schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "expected_schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "migration_receipt_count": 1,
        "integrity_check": "ok",
        "foreign_key_violation_count": 0,
        "trusted_receipt_chain_valid": False,
        "trusted_receipt_chain_failure_code": (
            "chain_not_established"
        ),
        "trusted_receipt_chain_tip": (
            receipt.receipt_id
        ),
        "trusted_receipt_chain_length": 1,
        "trusted_receipt_lineage_epoch": None,
        "checks": {
            "database_exists": True,
            "database_readable": True,
            "schema_current": True,
            "integrity_valid": True,
            "foreign_keys_valid": True,
            "migration_receipt_present": True,
            "trusted_receipt_present": True,
            "trusted_receipt_chain_valid": False,
            "trusted_receipt_compatible": True,
        },
        "warnings": [
            "SQLite trusted-store receipt is valid "
            "legacy version 1, but version 2 receipt "
            "lineage is not established."
        ],
        "errors": [],
    }


def test_missing_receipt_readiness_full_contract(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"
    SQLiteRepositoryEvidenceStore(database_path)

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.model_dump(mode="json") == {
        "status": "misconfigured",
        "backend": "sqlite",
        "writable_store_initialized": True,
        "schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "expected_schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "migration_receipt_count": 0,
        "integrity_check": "ok",
        "foreign_key_violation_count": 0,
        "trusted_receipt_chain_valid": False,
        "trusted_receipt_chain_failure_code": (
            "chain_not_established"
        ),
        "trusted_receipt_chain_tip": None,
        "trusted_receipt_chain_length": 0,
        "trusted_receipt_lineage_epoch": None,
        "checks": {
            "database_exists": True,
            "database_readable": True,
            "schema_current": True,
            "integrity_valid": True,
            "foreign_keys_valid": True,
            "migration_receipt_present": False,
            "trusted_receipt_present": False,
            "trusted_receipt_chain_valid": False,
            "trusted_receipt_compatible": False,
        },
        "warnings": [],
        "errors": [
            "SQLite database has no trusted-store "
            "initialization or migration receipt."
        ],
    }


def test_malformed_receipt_readiness_full_contract(
    tmp_path: Path,
):
    database_path = tmp_path / "malformed.db"
    receipt = initialize_fresh_trusted_store(
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

    readiness = assess_sqlite_database_readiness(
        database_path
    )

    assert readiness.model_dump(mode="json") == {
        "status": "misconfigured",
        "backend": "sqlite",
        "writable_store_initialized": True,
        "schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "expected_schema_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "migration_receipt_count": 1,
        "integrity_check": "ok",
        "foreign_key_violation_count": 0,
        "trusted_receipt_chain_valid": False,
        "trusted_receipt_chain_failure_code": (
            "receipt_parse_failure"
        ),
        "trusted_receipt_chain_tip": (
            receipt.receipt_id
        ),
        "trusted_receipt_chain_length": 0,
        "trusted_receipt_lineage_epoch": None,
        "checks": {
            "database_exists": True,
            "database_readable": True,
            "schema_current": True,
            "integrity_valid": True,
            "foreign_keys_valid": True,
            "migration_receipt_present": True,
            "trusted_receipt_present": True,
            "trusted_receipt_chain_valid": False,
            "trusted_receipt_compatible": False,
        },
        "warnings": [],
        "errors": [
            "SQLite trusted-store receipt data "
            "could not be parsed."
        ],
    }
