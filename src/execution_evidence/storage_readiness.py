from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
    RepositoryEvidenceStoreError,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.trusted_store import (
    TrustedStoreInitializationError,
    load_valid_trusted_receipt,
)


StorageReadinessStatus = Literal[
    "ready",
    "degraded",
    "misconfigured",
]


class ExecutionEvidenceStorageReadiness(
    BaseModel
):
    status: StorageReadinessStatus
    backend: Literal["json", "sqlite"]
    writable_store_initialized: bool
    schema_version: Optional[int] = None
    expected_schema_version: Optional[int] = None
    migration_receipt_count: Optional[int] = None
    integrity_check: Optional[str] = None
    foreign_key_violation_count: Optional[int] = None
    checks: Dict[str, bool] = Field(
        default_factory=dict
    )
    warnings: List[str] = Field(
        default_factory=list
    )
    errors: List[str] = Field(
        default_factory=list
    )


def assess_execution_evidence_storage_readiness(
    store,
) -> ExecutionEvidenceStorageReadiness:
    if isinstance(
        store,
        JsonRepositoryEvidenceStore,
    ):
        return _assess_json_store(store)

    if isinstance(
        store,
        SQLiteRepositoryEvidenceStore,
    ):
        return assess_sqlite_database_readiness(
            store.path
        )

    return ExecutionEvidenceStorageReadiness(
        status="misconfigured",
        backend="json",
        writable_store_initialized=False,
        checks={
            "supported_store_type": False,
        },
        errors=[
            "Unsupported execution evidence store type."
        ],
    )


def _assess_json_store(
    store: JsonRepositoryEvidenceStore,
) -> ExecutionEvidenceStorageReadiness:
    exists = store.path.is_file()

    try:
        store.list_repository_keys()
    except RepositoryEvidenceStoreError:
        return ExecutionEvidenceStorageReadiness(
            status="misconfigured",
            backend="json",
            writable_store_initialized=exists,
            checks={
                "store_readable": False,
            },
            errors=[
                "JSON execution evidence storage "
                "could not be read or validated."
            ],
        )

    return ExecutionEvidenceStorageReadiness(
        status="ready",
        backend="json",
        writable_store_initialized=exists,
        checks={
            "store_readable": True,
            "schema_valid": True,
        },
    )


def assess_sqlite_database_readiness(
    database_path: Path | str,
) -> ExecutionEvidenceStorageReadiness:
    path = Path(database_path)

    if not path.is_file():
        return ExecutionEvidenceStorageReadiness(
            status="misconfigured",
            backend="sqlite",
            writable_store_initialized=False,
            expected_schema_version=(
                CURRENT_SQLITE_SCHEMA_VERSION
            ),
            checks={
                "database_exists": False,
            },
            errors=[
                "SQLite execution evidence database "
                "does not exist."
            ],
        )

    connection = None

    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=5.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row

        schema_row = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
                AS version
            FROM execution_evidence_schema_migrations
            """
        ).fetchone()

        schema_version = (
            int(schema_row["version"])
            if schema_row is not None
            else 0
        )

        integrity_rows = connection.execute(
            "PRAGMA integrity_check"
        ).fetchall()
        integrity_messages = [
            str(row[0])
            for row in integrity_rows
        ]
        integrity_check = ",".join(
            integrity_messages
        )

        foreign_key_violations = (
            connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
        )
        foreign_key_violation_count = len(
            foreign_key_violations
        )

        receipt_row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM execution_evidence_import_receipts
            """
        ).fetchone()
        receipt_count = (
            int(receipt_row["count"])
            if receipt_row is not None
            else 0
        )
    except sqlite3.Error:
        return ExecutionEvidenceStorageReadiness(
            status="misconfigured",
            backend="sqlite",
            writable_store_initialized=True,
            expected_schema_version=(
                CURRENT_SQLITE_SCHEMA_VERSION
            ),
            checks={
                "database_exists": True,
                "database_readable": False,
            },
            errors=[
                "SQLite execution evidence database "
                "could not be read or validated."
            ],
        )
    finally:
        if connection is not None:
            connection.close()

    schema_current = (
        schema_version
        == CURRENT_SQLITE_SCHEMA_VERSION
    )
    integrity_valid = (
        integrity_messages == ["ok"]
    )
    foreign_keys_valid = (
        foreign_key_violation_count == 0
    )
    trusted_receipt = None
    trusted_receipt_validation_failed = False

    if (
        schema_current
        and integrity_valid
        and foreign_keys_valid
    ):
        try:
            trusted_receipt = (
                load_valid_trusted_receipt(
                    path
                )
            )
        except TrustedStoreInitializationError:
            trusted_receipt_validation_failed = True

    trusted_receipt_present = (
        trusted_receipt is not None
    )

    errors: List[str] = []
    warnings: List[str] = []

    if not schema_current:
        errors.append(
            "SQLite execution evidence schema "
            "version is not current."
        )

    if not integrity_valid:
        errors.append(
            "SQLite integrity validation failed."
        )

    if not foreign_keys_valid:
        errors.append(
            "SQLite foreign-key validation failed."
        )

    if trusted_receipt_validation_failed:
        errors.append(
            "SQLite trusted-store receipts could "
            "not be validated."
        )
    elif not trusted_receipt_present:
        errors.append(
            "SQLite database has no valid trusted-store "
            "initialization or migration receipt."
        )

    if errors:
        status: StorageReadinessStatus = (
            "misconfigured"
        )
    elif warnings:
        status = "degraded"
    else:
        status = "ready"

    return ExecutionEvidenceStorageReadiness(
        status=status,
        backend="sqlite",
        writable_store_initialized=True,
        schema_version=schema_version,
        expected_schema_version=(
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        migration_receipt_count=receipt_count,
        integrity_check=integrity_check,
        foreign_key_violation_count=(
            foreign_key_violation_count
        ),
        checks={
            "database_exists": True,
            "database_readable": True,
            "schema_current": schema_current,
            "integrity_valid": integrity_valid,
            "foreign_keys_valid": (
                foreign_keys_valid
            ),
            "migration_receipt_present": (
                trusted_receipt_present
            ),
            "trusted_receipt_present": (
                trusted_receipt_present
            ),
        },
        warnings=warnings,
        errors=errors,
    )
