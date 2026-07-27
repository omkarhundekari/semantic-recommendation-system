from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    Field,
)

from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
    RepositoryEvidenceStoreError,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.sqlite_trusted_store_snapshot import (
    SQLiteTrustedStoreRawSnapshot,
    capture_sqlite_trusted_store_snapshot,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_VERSION,
)
from execution_evidence.trusted_receipt_chain import (
    TrustedReceiptChainFailureCode,
    validate_trusted_receipt_chain,
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
    trusted_receipt_chain_valid: Optional[bool] = None
    trusted_receipt_chain_failure_code: Optional[str] = None
    trusted_receipt_chain_tip: Optional[str] = None
    trusted_receipt_chain_length: Optional[int] = None
    trusted_receipt_lineage_epoch: Optional[int] = None
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


def derive_sqlite_storage_readiness(
    snapshot: SQLiteTrustedStoreRawSnapshot,
) -> ExecutionEvidenceStorageReadiness:
    """Derive readiness from an immutable SQLite snapshot."""
    schema_version = snapshot.schema_migration_version
    user_version = snapshot.user_version
    receipt_count = snapshot.receipt_row_count

    if schema_version is None:
        schema_version_value = 0
    else:
        schema_version_value = schema_version

    if user_version is None:
        user_version_value = 0
    else:
        user_version_value = user_version

    schema_current = (
        snapshot.schema_migration_version_read_error
        is None
        and snapshot.user_version_read_error is None
        and schema_version
        == CURRENT_SQLITE_SCHEMA_VERSION
        and user_version
        == CURRENT_SQLITE_SCHEMA_VERSION
    )

    integrity_valid = (
        snapshot.integrity_read_error is None
        and list(snapshot.integrity_messages)
        == ["ok"]
    )

    foreign_keys_valid = (
        snapshot.foreign_key_read_error is None
        and len(snapshot.foreign_key_violations) == 0
    )

    receipt_present = (
        receipt_count is not None
        and receipt_count > 0
    )

    errors: List[str] = []
    warnings: List[str] = []

    chain_valid: Optional[bool] = None
    chain_failure_code: Optional[str] = None
    chain_tip: Optional[str] = None
    chain_length: Optional[int] = None
    lineage_epoch: Optional[int] = None
    receipt_compatible = False

    parse_failure = bool(
        snapshot.unparseable_receipt_rows
    )

    if (
        schema_current
        and integrity_valid
        and foreign_keys_valid
    ):
        if parse_failure:
            first_malformed = min(
                snapshot.unparseable_receipt_rows,
                key=lambda item: (
                    item.snapshot_row_index
                ),
            )
            chain_valid = False
            chain_failure_code = (
                "receipt_parse_failure"
            )
            chain_tip = first_malformed.receipt_id
            chain_length = (
                first_malformed.snapshot_row_index
            )
        else:
            chain_result = (
                validate_trusted_receipt_chain(
                    snapshot.receipts,
                    user_version=user_version_value,
                )
            )
            chain_valid = chain_result.valid
            chain_tip = (
                chain_result.authoritative_tip
            )
            chain_length = (
                chain_result.chain_length
            )
            lineage_epoch = (
                chain_result.lineage_epoch
            )

            if chain_result.failure is not None:
                chain_failure_code = (
                    chain_result.failure.code.value
                )

            if chain_result.valid:
                receipt_compatible = True
            elif (
                chain_result.failure is not None
                and chain_result.failure.code
                == TrustedReceiptChainFailureCode
                .CHAIN_NOT_ESTABLISHED
                and chain_result.chain_length == 1
                and chain_result.authoritative_tip
                is not None
            ):
                authoritative_receipt = next(
                    (
                        receipt
                        for receipt in snapshot.receipts
                        if receipt.receipt_id
                        == chain_result.authoritative_tip
                    ),
                    None,
                )

                if (
                    authoritative_receipt is not None
                    and authoritative_receipt
                    .receipt_version
                    == MIGRATION_RECEIPT_VERSION
                ):
                    receipt_compatible = True
                    warnings.append(
                        "SQLite trusted-store receipt "
                        "is valid legacy version 1, but "
                        "version 2 receipt lineage is "
                        "not established."
                    )

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

    if (
        schema_current
        and integrity_valid
        and foreign_keys_valid
    ):
        if parse_failure:
            errors.append(
                "SQLite trusted-store receipt data "
                "could not be parsed."
            )
        elif not receipt_present:
            errors.append(
                "SQLite database has no trusted-store "
                "initialization or migration receipt."
            )
        elif not receipt_compatible:
            errors.append(
                "SQLite trusted-store receipt chain "
                "could not be validated."
            )

    if errors:
        status: StorageReadinessStatus = (
            "misconfigured"
        )
    elif chain_valid is True:
        status = "ready"
    elif receipt_compatible:
        status = "degraded"
    else:
        status = "misconfigured"

    if status == "ready" and chain_valid is not True:
        raise AssertionError(
            "Ready SQLite storage requires a valid "
            "trusted receipt chain."
        )

    if chain_valid is True and status != "ready":
        raise AssertionError(
            "A valid trusted receipt chain must produce "
            "ready SQLite storage."
        )

    return ExecutionEvidenceStorageReadiness(
        status=status,
        backend="sqlite",
        writable_store_initialized=True,
        schema_version=schema_version,
        expected_schema_version=(
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        migration_receipt_count=receipt_count,
        integrity_check=",".join(
            snapshot.integrity_messages
        ),
        foreign_key_violation_count=len(
            snapshot.foreign_key_violations
        ),
        trusted_receipt_chain_valid=chain_valid,
        trusted_receipt_chain_failure_code=(
            chain_failure_code
        ),
        trusted_receipt_chain_tip=chain_tip,
        trusted_receipt_chain_length=(
            chain_length
        ),
        trusted_receipt_lineage_epoch=(
            lineage_epoch
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
                receipt_present
            ),
            "trusted_receipt_present": (
                receipt_present
            ),
            "trusted_receipt_chain_valid": (
                chain_valid is True
            ),
            "trusted_receipt_compatible": (
                receipt_compatible
            ),
        },
        warnings=warnings,
        errors=errors,
    )


def _raise_for_legacy_snapshot_read_failure(
    snapshot: SQLiteTrustedStoreRawSnapshot,
) -> None:
    missing_tables = [
        item.table_name
        for item in snapshot.required_tables
        if not item.present
    ]

    if missing_tables:
        raise sqlite3.OperationalError(
            "Missing required trusted-store tables: "
            + ", ".join(missing_tables)
        )

    read_errors = (
        snapshot.schema_migration_version_read_error,
        snapshot.user_version_read_error,
        snapshot.integrity_read_error,
        snapshot.foreign_key_read_error,
        snapshot.receipts_read_error,
    )

    first_error = next(
        (
            error
            for error in read_errors
            if error is not None
        ),
        None,
    )

    if first_error is not None:
        raise sqlite3.DatabaseError(
            first_error.message
        )


def assess_sqlite_connection_readiness(
    connection: sqlite3.Connection,
) -> ExecutionEvidenceStorageReadiness:
    """Assess SQLite readiness inside a caller-owned transaction."""
    if not connection.in_transaction:
        raise ValueError(
            "SQLite readiness assessment requires "
            "an active caller-owned transaction."
        )

    snapshot = capture_sqlite_trusted_store_snapshot(
        connection
    )

    # Preserve the established connection-level contract
    # during the pure derivation extraction. Structural and
    # SQLite read failures remain caller-visible exceptions.
    _raise_for_legacy_snapshot_read_failure(
        snapshot
    )

    return derive_sqlite_storage_readiness(
        snapshot
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
        connection.execute("BEGIN")

        return assess_sqlite_connection_readiness(
            connection
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
            try:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
            finally:
                connection.close()
