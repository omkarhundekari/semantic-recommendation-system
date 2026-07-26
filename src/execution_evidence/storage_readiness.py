from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Literal, Optional

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
)

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
from execution_evidence.store_migration import (
    MIGRATION_RECEIPT_VERSION,
    RepositoryEvidenceMigrationReceipt,
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
        connection.execute("BEGIN")

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

        user_version_row = connection.execute(
            "PRAGMA user_version"
        ).fetchone()
        user_version = (
            int(user_version_row[0])
            if user_version_row is not None
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

        receipt_rows = connection.execute(
            """
            SELECT
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
            FROM execution_evidence_import_receipts
            ORDER BY created_at, receipt_id
            """
        ).fetchall()
        receipt_count = len(receipt_rows)
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
        and user_version
        == CURRENT_SQLITE_SCHEMA_VERSION
    )
    integrity_valid = (
        integrity_messages == ["ok"]
    )
    foreign_keys_valid = (
        foreign_key_violation_count == 0
    )
    receipt_present = receipt_count > 0

    errors: List[str] = []
    warnings: List[str] = []

    chain_valid: Optional[bool] = None
    chain_failure_code: Optional[str] = None
    chain_tip: Optional[str] = None
    chain_length: Optional[int] = None
    lineage_epoch: Optional[int] = None
    receipt_compatible = False

    parsed_receipts = []
    parse_failure = False

    if (
        schema_current
        and integrity_valid
        and foreign_keys_valid
    ):
        for row in receipt_rows:
            try:
                parsed_receipts.append(
                    RepositoryEvidenceMigrationReceipt(
                        **dict(row)
                    )
                )
            except (
                ValidationError,
                TypeError,
                ValueError,
            ):
                parse_failure = True
                chain_valid = False
                chain_failure_code = (
                    "receipt_parse_failure"
                )
                chain_tip = (
                    str(row["receipt_id"])
                    if row["receipt_id"] is not None
                    else None
                )
                chain_length = len(
                    parsed_receipts
                )
                break

        if not parse_failure:
            chain_result = (
                validate_trusted_receipt_chain(
                    parsed_receipts,
                    user_version=user_version,
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
                        for receipt in parsed_receipts
                        if receipt.receipt_id
                        == chain_result.authoritative_tip
                    ),
                    None,
                )

                if (
                    authoritative_receipt
                    is not None
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
        integrity_check=integrity_check,
        foreign_key_violation_count=(
            foreign_key_violation_count
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
