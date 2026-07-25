from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)
from execution_evidence.store_migration import (
    CANONICAL_AGGREGATE_VERSION,
    MIGRATION_RECEIPT_VERSION,
    MIGRATION_RECEIPT_V2_VERSION,
    MIGRATION_RECEIPT_KINDS,
    RepositoryEvidenceMigrationError,
    RepositoryEvidenceMigrationLock,
    RepositoryEvidenceMigrationReceipt,
    RepositoryEvidenceMigrationReport,
    build_migration_receipt,
    build_repository_evidence_root_hash,
    calculate_migration_receipt_id,
    load_repository_evidence_snapshot,
    persist_migration_receipt,
    verify_migration_receipt,
    verify_repository_evidence_migration,
)


FRESH_INIT_SOURCE_TYPE = "fresh_init"
JSON_IMPORT_SOURCE_TYPE = "json_import"
LEGACY_JSON_IMPORT_SOURCE_TYPE = "json"
SQLITE_UPGRADE_SOURCE_TYPE = "sqlite_upgrade"

TRUSTED_STORE_RECEIPT_SOURCE_TYPES: Set[str] = {
    FRESH_INIT_SOURCE_TYPE,
    JSON_IMPORT_SOURCE_TYPE,
    LEGACY_JSON_IMPORT_SOURCE_TYPE,
    SQLITE_UPGRADE_SOURCE_TYPE,
}

FRESH_INIT_SOURCE_IDENTIFIER = "solvyn:fresh-init"
FRESH_INIT_WAIT_SECONDS = 5.0
FRESH_INIT_POLL_INTERVAL_SECONDS = 0.05


class TrustedStoreInitializationError(RuntimeError):
    pass


def build_fresh_init_report(
) -> RepositoryEvidenceMigrationReport:
    return RepositoryEvidenceMigrationReport(
        source_type=FRESH_INIT_SOURCE_TYPE,
        destination_type="sqlite",
        repository_count=0,
        evidence_count=0,
        attribution_count=0,
        root_hash=build_repository_evidence_root_hash(
            []
        ),
        records=[],
        integrity_check="ok",
        foreign_key_violation_count=0,
        relational_counts={
            "repositories": 0,
            "evidence_items": 0,
            "evidence_attributions": 0,
        },
        verified=True,
        dry_run=False,
    )


def build_fresh_init_receipt(
    *,
    created_at: str,
) -> RepositoryEvidenceMigrationReceipt:
    return build_migration_receipt(
        report=build_fresh_init_report(),
        source_identifier=(
            FRESH_INIT_SOURCE_IDENTIFIER
        ),
        created_at=created_at,
    )


def initialize_fresh_trusted_store(
    database_path: Path | str,
    *,
    created_at: Optional[str] = None,
) -> RepositoryEvidenceMigrationReceipt:
    path = Path(database_path)
    lock_path = path.with_name(
        f".{path.name}.migration.lock"
    )
    timestamp = (
        created_at
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    try:
        with RepositoryEvidenceMigrationLock(
            lock_path
        ):
            if path.exists():
                existing = (
                    load_valid_trusted_receipt(
                        path
                    )
                )

                if existing is not None:
                    return existing

                raise TrustedStoreInitializationError(
                    "Existing SQLite database does not "
                    "contain a valid trusted-store receipt."
                )

            initialize_execution_evidence_database(
                path
            )

            receipt = build_fresh_init_receipt(
                created_at=timestamp,
            )

            persist_migration_receipt(
                database_path=path,
                receipt=receipt,
            )
            verify_migration_receipt(
                database_path=path,
                receipt=receipt,
            )

            stored = load_valid_trusted_receipt(
                path
            )

            if stored != receipt:
                raise TrustedStoreInitializationError(
                    "Fresh SQLite initialization did "
                    "not produce a valid trusted receipt."
                )

            return receipt
    except RepositoryEvidenceMigrationError as error:
        if "appears to be running" not in str(
            error
        ):
            raise TrustedStoreInitializationError(
                "Could not initialize the trusted "
                "SQLite store."
            ) from error

        return _wait_for_concurrent_initialization(
            path
        )


def upgrade_trusted_sqlite_store(
    database_path: Path | str,
    *,
    created_at: Optional[str] = None,
    backup_path: Optional[Path | str] = None,
) -> RepositoryEvidenceMigrationReceipt:
    from execution_evidence.sqlite_store import (
        SQLiteRepositoryEvidenceStore,
    )

    path = Path(database_path)
    lock_path = path.with_name(
        f".{path.name}.migration.lock"
    )
    timestamp = (
        created_at
        or datetime.now(
            timezone.utc
        ).isoformat()
    )

    if not path.is_file():
        raise TrustedStoreInitializationError(
            "Trusted SQLite upgrade requires an "
            "existing database."
        )

    try:
        with RepositoryEvidenceMigrationLock(
            lock_path
        ):
            previous_receipt = (
                load_valid_trusted_receipt(path)
            )

            if previous_receipt is None:
                raise TrustedStoreInitializationError(
                    "Existing SQLite database does not "
                    "contain a valid trusted-store receipt."
                )

            connection = (
                connect_execution_evidence_database(path)
            )

            try:
                previous_version = (
                    get_execution_evidence_schema_version(
                        connection
                    )
                )
            finally:
                connection.close()

            if (
                previous_version
                == CURRENT_SQLITE_SCHEMA_VERSION
            ):
                return previous_receipt

            if (
                previous_version
                > CURRENT_SQLITE_SCHEMA_VERSION
            ):
                raise TrustedStoreInitializationError(
                    "SQLite database schema is newer "
                    "than this application supports."
                )

            source_store = (
                SQLiteRepositoryEvidenceStore(
                    path,
                    initialize_schema=False,
                )
            )
            source_records = (
                load_repository_evidence_snapshot(
                    source_store
                )
            )
            source_root_hash = (
                build_repository_evidence_root_hash(
                    source_records
                )
            )

            resolved_backup_path = (
                Path(backup_path)
                if backup_path is not None
                else path.with_name(
                    f"{path.stem}.pre-v"
                    f"{CURRENT_SQLITE_SCHEMA_VERSION}."
                    f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
                    f"{path.suffix}"
                )
            )

            if resolved_backup_path.exists():
                raise TrustedStoreInitializationError(
                    "Trusted SQLite upgrade backup "
                    "already exists."
                )

            source_connection = (
                connect_execution_evidence_database(path)
            )

            try:
                source_connection.execute(
                    "PRAGMA wal_checkpoint(FULL)"
                )
                backup_connection = sqlite3.connect(
                    str(resolved_backup_path)
                )

                try:
                    source_connection.backup(
                        backup_connection
                    )
                finally:
                    backup_connection.close()
            except sqlite3.Error as error:
                raise TrustedStoreInitializationError(
                    "Could not create the trusted "
                    "SQLite upgrade backup."
                ) from error
            finally:
                source_connection.close()

            try:
                initialize_execution_evidence_database(
                    path
                )

                destination = (
                    SQLiteRepositoryEvidenceStore(
                        path,
                        initialize_schema=False,
                    )
                )
                verification = (
                    verify_repository_evidence_migration(
                        source_records=source_records,
                        destination=destination,
                    )
                )
                report = verification.model_copy(
                    update={
                        "source_type": (
                            SQLITE_UPGRADE_SOURCE_TYPE
                        ),
                        "destination_type": "sqlite",
                        "root_hash": source_root_hash,
                        "verified": True,
                        "dry_run": False,
                    },
                    deep=True,
                )

                receipt = build_migration_receipt(
                    report=report,
                    source_identifier=(
                        "solvyn:sqlite-upgrade:"
                        f"{previous_receipt.receipt_id}:"
                        f"v{previous_version}->"
                        f"v{CURRENT_SQLITE_SCHEMA_VERSION}"
                    ),
                    created_at=timestamp,
                )

                persist_migration_receipt(
                    database_path=path,
                    receipt=receipt,
                )
                verify_migration_receipt(
                    database_path=path,
                    receipt=receipt,
                )

                stored = load_valid_trusted_receipt(
                    path
                )

                if stored != receipt:
                    raise TrustedStoreInitializationError(
                        "SQLite upgrade did not produce "
                        "a valid trusted receipt."
                    )

                final_connection = (
                    connect_execution_evidence_database(
                        path
                    )
                )

                try:
                    final_version = (
                        get_execution_evidence_schema_version(
                            final_connection
                        )
                    )
                finally:
                    final_connection.close()

                if (
                    final_version
                    != CURRENT_SQLITE_SCHEMA_VERSION
                ):
                    raise TrustedStoreInitializationError(
                        "SQLite upgrade did not reach the "
                        "current schema version."
                    )
            except Exception as upgrade_error:
                try:
                    restore_source = sqlite3.connect(
                        str(resolved_backup_path)
                    )
                    restore_destination = sqlite3.connect(
                        str(path)
                    )

                    try:
                        restore_source.backup(
                            restore_destination
                        )
                    finally:
                        restore_destination.close()
                        restore_source.close()

                    restored_receipt = (
                        load_valid_trusted_receipt(path)
                    )

                    if restored_receipt != previous_receipt:
                        raise TrustedStoreInitializationError(
                            "SQLite upgrade failed and the "
                            "trusted backup could not be "
                            "verified after restoration."
                        )
                except Exception as restore_error:
                    raise TrustedStoreInitializationError(
                        "SQLite upgrade failed and automatic "
                        "backup restoration also failed."
                    ) from restore_error

                if isinstance(
                    upgrade_error,
                    TrustedStoreInitializationError,
                ):
                    raise upgrade_error

                if isinstance(
                    upgrade_error,
                    RepositoryEvidenceMigrationError,
                ):
                    raise TrustedStoreInitializationError(
                        "Could not upgrade the trusted "
                        "SQLite store."
                    ) from upgrade_error

                raise TrustedStoreInitializationError(
                    "Trusted SQLite upgrade failed. The "
                    "original database was restored."
                ) from upgrade_error

            return receipt
    except RepositoryEvidenceMigrationError as error:
        raise TrustedStoreInitializationError(
            "Could not upgrade the trusted SQLite "
            "store."
        ) from error


def load_valid_trusted_receipt(
    database_path: Path | str,
) -> Optional[
    RepositoryEvidenceMigrationReceipt
]:
    path = Path(database_path)

    if not path.is_file():
        return None

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        rows = connection.execute(
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
            ORDER BY created_at DESC, receipt_id
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise TrustedStoreInitializationError(
            "Could not inspect trusted-store "
            "receipts."
        ) from error
    finally:
        connection.close()

    for row in rows:
        receipt = (
            RepositoryEvidenceMigrationReceipt(
                **dict(row)
            )
        )

        if validate_trusted_store_receipt(
            receipt
        ):
            return receipt

    return None





def validate_trusted_store_receipt(
    receipt: RepositoryEvidenceMigrationReceipt,
) -> bool:
    if receipt.receipt_version not in {
        MIGRATION_RECEIPT_VERSION,
        MIGRATION_RECEIPT_V2_VERSION,
    }:
        return False

    if (
        receipt.receipt_version
        == MIGRATION_RECEIPT_VERSION
    ):
        if any(
            value is not None
            for value in (
                receipt.receipt_kind,
                receipt.predecessor_receipt_id,
                receipt.schema_version_from,
                receipt.schema_version_to,
                receipt.lineage_epoch,
            )
        ):
            return False
    else:
        if (
            receipt.receipt_kind
            not in MIGRATION_RECEIPT_KINDS
            or receipt.schema_version_to is None
            or receipt.lineage_epoch is None
            or receipt.lineage_epoch < 1
        ):
            return False

        if receipt.receipt_kind == "root":
            if (
                receipt.predecessor_receipt_id
                is not None
                or receipt.schema_version_from
                is not None
            ):
                return False
        elif (
            receipt.predecessor_receipt_id
            is None
            or receipt.schema_version_from
            is None
            or receipt.schema_version_to
            <= receipt.schema_version_from
        ):
            return False

    if (
        receipt.source_type
        not in TRUSTED_STORE_RECEIPT_SOURCE_TYPES
    ):
        return False

    try:
        report_payload = json.loads(
            receipt.deterministic_report_json
        )
        report = (
            RepositoryEvidenceMigrationReport
            .model_validate(report_payload)
        )
    except (
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ):
        return False

    if report.source_type != receipt.source_type:
        return False

    if report.destination_type != "sqlite":
        return False

    if not report.verified or report.dry_run:
        return False

    if report.integrity_check != "ok":
        return False

    if report.foreign_key_violation_count != 0:
        return False

    if (
        report.canonicalization_version
        != receipt.canonicalization_version
    ):
        return False

    if (
        report.report_version
        != receipt.report_version
    ):
        return False

    if report.root_hash != receipt.source_root_hash:
        return False

    if (
        report.repository_count
        != receipt.repository_count
    ):
        return False

    if (
        report.evidence_count
        != receipt.evidence_count
    ):
        return False

    if (
        report.attribution_count
        != receipt.attribution_count
    ):
        return False

    if (
        receipt.canonicalization_version
        != CANONICAL_AGGREGATE_VERSION
    ):
        return False

    if (
        receipt.source_type
        == FRESH_INIT_SOURCE_TYPE
    ):
        if (
            receipt.source_identifier
            != FRESH_INIT_SOURCE_IDENTIFIER
        ):
            return False

        if any(
            (
                receipt.repository_count,
                receipt.evidence_count,
                receipt.attribution_count,
            )
        ):
            return False

        if (
            receipt.source_root_hash
            != build_repository_evidence_root_hash(
                []
            )
        ):
            return False

    try:
        expected_receipt_id = (
            calculate_migration_receipt_id(
                receipt
            )
        )
    except RepositoryEvidenceMigrationError:
        return False

    return (
        expected_receipt_id
        == receipt.receipt_id
    )


from execution_evidence.trusted_receipt_chain import (
    MAX_TRUSTED_RECEIPT_CHAIN_ROWS,
    TrustedReceiptChainFailure,
    TrustedReceiptChainFailureCode,
    TrustedReceiptChainValidationResult,
    validate_trusted_receipt_chain,
)


def _wait_for_concurrent_initialization(
    path: Path,
) -> RepositoryEvidenceMigrationReceipt:
    deadline = (
        time.monotonic()
        + FRESH_INIT_WAIT_SECONDS
    )

    while time.monotonic() < deadline:
        try:
            receipt = (
                load_valid_trusted_receipt(
                    path
                )
            )
        except TrustedStoreInitializationError:
            receipt = None

        if receipt is not None:
            return receipt

        time.sleep(
            FRESH_INIT_POLL_INTERVAL_SECONDS
        )

    raise TrustedStoreInitializationError(
        "Timed out waiting for concurrent "
        "trusted-store initialization."
    )
