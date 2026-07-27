from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from execution_evidence.store_migration import (
    build_migration_receipt,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)

from execution_evidence.trusted_store import (
    FRESH_INIT_SOURCE_TYPE,
    JSON_IMPORT_SOURCE_TYPE,
    LEGACY_JSON_IMPORT_SOURCE_TYPE,
    SQLITE_UPGRADE_SOURCE_TYPE,
    TrustedStoreInitializationError,
    build_fresh_init_report,
    build_fresh_init_receipt,
    initialize_fresh_trusted_store,
    load_valid_trusted_receipt,
    upgrade_trusted_sqlite_store,
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



def test_sqlite_upgrade_receipt_is_recognized():
    report = build_fresh_init_report().model_copy(
        update={
            "source_type": SQLITE_UPGRADE_SOURCE_TYPE,
        }
    )
    receipt = build_migration_receipt(
        report=report,
        source_identifier="solvyn.db:schema-6-to-7",
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



def test_upgrade_trusted_sqlite_store_preserves_data(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    backup_path = tmp_path / "solvyn.pre-upgrade.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-14T12:00:00+00:00",
    )

    import execution_evidence.trusted_store as module

    monkeypatch.setattr(
        module,
        "CURRENT_SQLITE_SCHEMA_VERSION",
        CURRENT_SQLITE_SCHEMA_VERSION + 1,
    )

    original_initialize = (
        module.initialize_execution_evidence_database
    )

    def apply_test_upgrade(path):
        connection = (
            connect_execution_evidence_database(path)
        )
        try:
            connection.execute(
                """
                INSERT INTO
                    execution_evidence_schema_migrations (
                        version,
                        name,
                        applied_at
                    )
                VALUES (?, ?, ?)
                """,
                (
                    CURRENT_SQLITE_SCHEMA_VERSION + 1,
                    "test_trusted_upgrade",
                    "2026-07-14T13:00:00+00:00",
                ),
            )
        finally:
            connection.close()

    monkeypatch.setattr(
        module,
        "initialize_execution_evidence_database",
        apply_test_upgrade,
    )

    receipt = upgrade_trusted_sqlite_store(
        database_path,
        created_at="2026-07-14T13:00:00+00:00",
        backup_path=backup_path,
    )

    assert receipt.source_type == "sqlite_upgrade"
    assert backup_path.is_file()
    assert (
        load_valid_trusted_receipt(database_path)
        == receipt
    )

    monkeypatch.setattr(
        module,
        "initialize_execution_evidence_database",
        original_initialize,
    )


def test_upgrade_current_trusted_store_is_idempotent(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    original = initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-14T12:00:00+00:00",
    )

    result = upgrade_trusted_sqlite_store(
        database_path,
        created_at="2026-07-14T13:00:00+00:00",
    )

    assert result == original
    assert list(
        tmp_path.glob("solvyn.pre-v*.db")
    ) == []


def test_upgrade_rejects_untrusted_database(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    with pytest.raises(
        TrustedStoreInitializationError,
        match="valid trusted-store receipt",
    ):
        upgrade_trusted_sqlite_store(
            database_path
        )



def test_upgrade_restores_backup_after_failure(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    backup_path = tmp_path / "solvyn.pre-upgrade.db"

    original_receipt = (
        initialize_fresh_trusted_store(
            database_path,
            created_at="2026-07-14T12:00:00+00:00",
        )
    )

    import execution_evidence.trusted_store as module

    target_version = (
        CURRENT_SQLITE_SCHEMA_VERSION + 1
    )

    monkeypatch.setattr(
        module,
        "CURRENT_SQLITE_SCHEMA_VERSION",
        target_version,
    )

    def apply_test_upgrade(path):
        connection = (
            connect_execution_evidence_database(path)
        )
        try:
            connection.execute(
                """
                INSERT INTO
                    execution_evidence_schema_migrations (
                        version,
                        name,
                        applied_at
                    )
                VALUES (?, ?, ?)
                """,
                (
                    target_version,
                    "test_failed_upgrade",
                    "2026-07-14T13:00:00+00:00",
                ),
            )
        finally:
            connection.close()

    def fail_verification(*args, **kwargs):
        raise RuntimeError(
            "forced verification failure"
        )

    monkeypatch.setattr(
        module,
        "initialize_execution_evidence_database",
        apply_test_upgrade,
    )
    monkeypatch.setattr(
        module,
        "verify_repository_evidence_migration",
        fail_verification,
    )

    with pytest.raises(
        TrustedStoreInitializationError,
        match="original database was restored",
    ):
        upgrade_trusted_sqlite_store(
            database_path,
            backup_path=backup_path,
        )

    assert backup_path.is_file()
    assert (
        load_valid_trusted_receipt(database_path)
        == original_receipt
    )

    connection = connect_execution_evidence_database(
        database_path
    )
    try:
        version = (
            get_execution_evidence_schema_version(
                connection
            )
        )
    finally:
        connection.close()

    assert version == CURRENT_SQLITE_SCHEMA_VERSION


def test_load_trusted_receipts_from_connection_requires_transaction(
    tmp_path: Path,
):
    from execution_evidence.sqlite_schema import (
        connect_execution_evidence_database,
    )
    from execution_evidence.trusted_store import (
        load_trusted_receipts_from_connection,
    )

    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        with pytest.raises(
            ValueError,
            match="active caller-owned transaction",
        ):
            load_trusted_receipts_from_connection(
                connection
            )
    finally:
        connection.close()


def test_load_trusted_receipts_from_connection_preserves_transaction(
    tmp_path: Path,
):
    from execution_evidence.sqlite_schema import (
        connect_execution_evidence_database,
    )
    from execution_evidence.trusted_store import (
        load_trusted_receipts_from_connection,
    )

    database_path = tmp_path / "solvyn.db"
    expected = initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        original_row_factory = connection.row_factory
        connection.execute("BEGIN")

        receipts = (
            load_trusted_receipts_from_connection(
                connection
            )
        )

        assert receipts == (expected,)
        assert connection.in_transaction is True
        assert (
            connection.row_factory
            is original_row_factory
        )
    finally:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
