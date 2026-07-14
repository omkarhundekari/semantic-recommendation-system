from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.store_migration import (
    CANONICAL_AGGREGATE_VERSION,
    MIGRATION_RECEIPT_VERSION,
    RepositoryEvidenceMigrationError,
    RepositoryEvidenceMigrationLock,
    RepositoryEvidenceMigrationReceipt,
    RepositoryEvidenceMigrationReport,
    build_migration_receipt,
    build_repository_evidence_root_hash,
    persist_migration_receipt,
    verify_migration_receipt,
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
                created_at
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
    if (
        receipt.receipt_version
        != MIGRATION_RECEIPT_VERSION
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

    expected_receipt_id = (
        _calculate_receipt_id(
            receipt
        )
    )

    return (
        expected_receipt_id
        == receipt.receipt_id
    )


def _calculate_receipt_id(
    receipt: RepositoryEvidenceMigrationReceipt,
) -> str:
    receipt_material = json.dumps(
        {
            "receipt_version": (
                receipt.receipt_version
            ),
            "source_type": (
                receipt.source_type
            ),
            "source_identifier": (
                receipt.source_identifier
            ),
            "source_root_hash": (
                receipt.source_root_hash
            ),
            "canonicalization_version": (
                receipt.canonicalization_version
            ),
            "report_version": (
                receipt.report_version
            ),
            "deterministic_report_json": (
                receipt.deterministic_report_json
            ),
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        receipt_material.encode("utf-8")
    ).hexdigest()


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
