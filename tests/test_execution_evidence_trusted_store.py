from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from execution_evidence.store_migration import (
    build_migration_receipt,
)
from execution_evidence.trusted_store import (
    FRESH_INIT_SOURCE_TYPE,
    JSON_IMPORT_SOURCE_TYPE,
    LEGACY_JSON_IMPORT_SOURCE_TYPE,
    build_fresh_init_report,
    build_fresh_init_receipt,
    initialize_fresh_trusted_store,
    load_valid_trusted_receipt,
    validate_trusted_store_receipt,
)


CREATED_AT = "2026-07-13T12:00:00+00:00"


def test_fresh_init_receipt_is_valid():
    receipt = build_fresh_init_receipt(
        created_at=CREATED_AT
    )

    assert (
        receipt.source_type
        == FRESH_INIT_SOURCE_TYPE
    )
    assert validate_trusted_store_receipt(
        receipt
    )


def test_tampered_receipt_id_is_rejected():
    receipt = build_fresh_init_receipt(
        created_at=CREATED_AT
    ).model_copy(
        update={
            "receipt_id": "0" * 64,
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_tampered_report_is_rejected():
    receipt = build_fresh_init_receipt(
        created_at=CREATED_AT
    ).model_copy(
        update={
            "deterministic_report_json": (
                '{"verified":false}'
            ),
        }
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_unknown_receipt_type_is_rejected():
    report = build_fresh_init_report().model_copy(
        update={
            "source_type": "unknown",
        }
    )
    receipt = build_migration_receipt(
        report=report,
        source_identifier="unknown",
        created_at=CREATED_AT,
    )

    assert not validate_trusted_store_receipt(
        receipt
    )


def test_json_import_receipt_is_recognized():
    report = build_fresh_init_report().model_copy(
        update={
            "source_type": (
                JSON_IMPORT_SOURCE_TYPE
            ),
        }
    )
    receipt = build_migration_receipt(
        report=report,
        source_identifier="repositories.json",
        created_at=CREATED_AT,
    )

    assert validate_trusted_store_receipt(
        receipt
    )


def test_legacy_json_receipt_remains_recognized():
    report = build_fresh_init_report().model_copy(
        update={
            "source_type": (
                LEGACY_JSON_IMPORT_SOURCE_TYPE
            ),
        }
    )
    receipt = build_migration_receipt(
        report=report,
        source_identifier="repositories.json",
        created_at=CREATED_AT,
    )

    assert validate_trusted_store_receipt(
        receipt
    )


def test_fresh_initialization_creates_trusted_store(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    receipt = initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    assert database_path.is_file()
    assert (
        receipt.source_type
        == FRESH_INIT_SOURCE_TYPE
    )
    assert (
        load_valid_trusted_receipt(
            database_path
        )
        == receipt
    )


def test_fresh_initialization_is_idempotent(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    first = initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )
    second = initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    assert second == first


def test_concurrent_fresh_initialization_is_idempotent(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    def initialize():
        return initialize_fresh_trusted_store(
            database_path,
            created_at=CREATED_AT,
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        receipts = list(
            executor.map(
                lambda _: initialize(),
                range(2),
            )
        )

    assert receipts[0] == receipts[1]
    assert (
        load_valid_trusted_receipt(
            database_path
        )
        == receipts[0]
    )
