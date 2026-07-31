from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
)
from execution_evidence.sqlite_trusted_store_snapshot import (
    SQLITE_TRUSTED_STORE_SNAPSHOT_FORMAT_VERSION,
    SQLiteForeignKeyViolation,
    SQLiteSnapshotReadError,
    SQLiteTrustedStoreRawSnapshot,
    capture_sqlite_trusted_store_snapshot,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)


CREATED_AT = "2026-07-13T12:00:00+00:00"


def _presence(snapshot):
    return {
        item.table_name: item.present
        for item in snapshot.required_tables
    }


def test_snapshot_capture_requires_active_transaction(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        with pytest.raises(
            ValueError,
            match="active caller-owned transaction",
        ):
            capture_sqlite_trusted_store_snapshot(
                connection
            )
    finally:
        connection.close()


def test_snapshot_captures_trusted_store_facts(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    receipt = initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )
    original_row_factory = lambda cursor, row: row
    connection.row_factory = original_row_factory

    try:
        connection.execute("BEGIN")

        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        assert snapshot.snapshot_format_version == (
            SQLITE_TRUSTED_STORE_SNAPSHOT_FORMAT_VERSION
        )
        assert _presence(snapshot) == {
            "execution_evidence_schema_migrations": True,
            "execution_evidence_import_receipts": True,
        }

        assert snapshot.schema_migration_version == (
            CURRENT_SQLITE_SCHEMA_VERSION
        )
        assert (
            snapshot.schema_migration_version_read_error
            is None
        )

        assert snapshot.user_version == (
            CURRENT_SQLITE_SCHEMA_VERSION
        )
        assert snapshot.user_version_read_error is None

        assert snapshot.data_version is not None
        assert snapshot.data_version >= 1
        assert snapshot.data_version_read_error is None

        assert snapshot.integrity_messages == (
            "ok",
        )
        assert snapshot.integrity_read_error is None

        assert snapshot.foreign_key_violations == ()
        assert snapshot.foreign_key_read_error is None

        assert snapshot.receipt_row_count == 1
        assert snapshot.receipts == (receipt,)
        assert (
            snapshot.unparseable_receipt_rows
            == ()
        )
        assert snapshot.receipts_read_error is None

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


def test_snapshot_distinguishes_missing_tables_from_empty_rows(
    tmp_path: Path,
):
    database_path = tmp_path / "uninitialized.db"

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        assert _presence(snapshot) == {
            "execution_evidence_schema_migrations": False,
            "execution_evidence_import_receipts": False,
        }
        assert snapshot.schema_migration_version is None
        assert (
            snapshot.schema_migration_version_read_error
            is None
        )

        assert snapshot.receipt_row_count is None
        assert snapshot.receipts == ()
        assert (
            snapshot.unparseable_receipt_rows
            == ()
        )
        assert snapshot.receipts_read_error is None

        assert snapshot.user_version == 0
        assert snapshot.integrity_messages == (
            "ok",
        )
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_snapshot_distinguishes_present_empty_receipt_table(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path)
    )
    try:
        connection.execute(
            """
            DELETE FROM execution_evidence_import_receipts
            """
        )
        connection.commit()
    finally:
        connection.close()

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        assert _presence(snapshot)[
            "execution_evidence_import_receipts"
        ] is True
        assert snapshot.receipt_row_count == 0
        assert snapshot.receipts == ()
        assert snapshot.receipts_read_error is None
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_snapshot_records_malformed_rows_without_omission(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
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
            WHERE receipt_id = ?
            """,
            (receipt.receipt_id,),
        )
        connection.commit()
    finally:
        connection.close()

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")

        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        assert snapshot.receipt_row_count == 1
        assert snapshot.receipts == ()
        assert len(
            snapshot.unparseable_receipt_rows
        ) == 1

        malformed = (
            snapshot.unparseable_receipt_rows[0]
        )
        assert malformed.receipt_rowid >= 1
        assert malformed.snapshot_row_index == 0
        assert malformed.receipt_id == (
            receipt.receipt_id
        )
        assert malformed.error_type == (
            "ValidationError"
        )

        assert snapshot.receipts_read_error is None
        assert connection.in_transaction is True
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_snapshot_records_receipt_read_failure(
    tmp_path: Path,
    monkeypatch,
):
    sqlite_corrupt_code = getattr(
        sqlite3,
        "SQLITE_CORRUPT",
        11,
    )

    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    def fail_receipt_read(*args, **kwargs):
        error = sqlite3.DatabaseError(
            "simulated receipt read failure"
        )
        error.sqlite_errorcode = (
            sqlite_corrupt_code
        )
        error.sqlite_errorname = (
            "SQLITE_CORRUPT"
        )
        raise error

    monkeypatch.setattr(
        "execution_evidence."
        "sqlite_trusted_store_snapshot."
        "load_trusted_receipt_rows_from_connection",
        fail_receipt_read,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        assert snapshot.receipt_row_count is None
        assert snapshot.receipts == ()
        assert (
            snapshot.unparseable_receipt_rows
            == ()
        )

        error = snapshot.receipts_read_error
        assert error is not None
        assert error.operation == (
            "read_trusted_receipts"
        )
        assert error.error_type == "DatabaseError"
        assert error.sqlite_errorcode == (
            sqlite_corrupt_code
        )
        assert error.sqlite_errorname == (
            "SQLITE_CORRUPT"
        )

        assert snapshot.integrity_messages == (
            "ok",
        )
        assert connection.in_transaction is True
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()


def test_raw_snapshot_is_immutable(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")
        snapshot = (
            capture_sqlite_trusted_store_snapshot(
                connection
            )
        )

        with pytest.raises(
            ValidationError,
            match="frozen",
        ):
            snapshot.user_version = 0

        with pytest.raises(
            ValidationError,
            match="frozen",
        ):
            snapshot.required_tables[
                0
            ].present = False
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()



def test_snapshot_rejects_partial_receipt_state():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteSnapshotReadError,
        SQLiteTablePresence,
        SQLiteTrustedStoreRawSnapshot,
    )
    from execution_evidence.store_migration import (
        RepositoryEvidenceMigrationReceipt,
    )

    import pytest

    with pytest.raises(ValueError):
        SQLiteTrustedStoreRawSnapshot(
            required_tables=(
                SQLiteTablePresence(
                    table_name="execution_evidence_schema_migrations",
                    present=True,
                ),
                SQLiteTablePresence(
                    table_name="execution_evidence_import_receipts",
                    present=True,
                ),
            ),
            schema_migration_version=14,
            schema_migration_version_read_error=None,
            user_version=14,
            user_version_read_error=None,
            data_version=1,
            data_version_read_error=None,
            integrity_messages=("ok",),
            integrity_read_error=None,
            foreign_key_violations=(),
            foreign_key_read_error=None,
            receipt_row_count=1,
            receipts=(
                RepositoryEvidenceMigrationReceipt(
                    migration_id="m1",
                    receipt_id="r1",
                    parent_receipt_id=None,
                    schema_version=1,
                    migration_name="x",
                    applied_at="2026-01-01T00:00:00+00:00",
                    checksum="abc",
                ),
            ),
            unparseable_receipt_rows=(),
            receipts_read_error=SQLiteSnapshotReadError(
                operation="read",
                error_type="DatabaseError",
                message="boom",
            ),
        )


def _valid_manual_snapshot_payload():
    from execution_evidence.sqlite_schema import (
        CURRENT_SQLITE_SCHEMA_VERSION,
    )
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteTablePresence,
    )

    return {
        "required_tables": (
            SQLiteTablePresence(
                table_name=(
                    "execution_evidence_"
                    "schema_migrations"
                ),
                present=True,
            ),
            SQLiteTablePresence(
                table_name=(
                    "execution_evidence_"
                    "import_receipts"
                ),
                present=True,
            ),
        ),
        "schema_migration_version": (
            CURRENT_SQLITE_SCHEMA_VERSION
        ),
        "schema_migration_version_read_error": None,
        "user_version": CURRENT_SQLITE_SCHEMA_VERSION,
        "user_version_read_error": None,
        "data_version": 1,
        "data_version_read_error": None,
        "integrity_messages": ("ok",),
        "integrity_read_error": None,
        "foreign_key_violations": (),
        "foreign_key_read_error": None,
        "receipt_row_count": 0,
        "receipts": (),
        "unparseable_receipt_rows": (),
        "receipts_read_error": None,
    }


@pytest.mark.parametrize(
    "updates",
    (
        {
            "user_version": None,
            "user_version_read_error": None,
        },
        {
            "data_version": 1,
            "data_version_read_error": (
                SQLiteSnapshotReadError(
                    operation="read_data_version",
                    error_type="DatabaseError",
                    message="boom",
                )
            ),
        },
        {
            "integrity_messages": ("ok",),
            "integrity_read_error": (
                SQLiteSnapshotReadError(
                    operation="run_integrity_check",
                    error_type="DatabaseError",
                    message="boom",
                )
            ),
        },
        {
            "foreign_key_violations": (
                SQLiteForeignKeyViolation(
                    table="child",
                    rowid=1,
                    parent="parent",
                    foreign_key_index=0,
                ),
            ),
            "foreign_key_read_error": (
                SQLiteSnapshotReadError(
                    operation="run_foreign_key_check",
                    error_type="DatabaseError",
                    message="boom",
                )
            ),
        },
    ),
)
def test_snapshot_rejects_conflicting_value_error_state(
    updates,
):
    payload = _valid_manual_snapshot_payload()
    payload.update(updates)

    with pytest.raises(ValueError):
        SQLiteTrustedStoreRawSnapshot(**payload)


def test_snapshot_rejects_receipt_facts_when_table_missing():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteTablePresence,
    )

    payload = _valid_manual_snapshot_payload()
    payload["required_tables"] = (
        payload["required_tables"][0],
        SQLiteTablePresence(
            table_name=(
                "execution_evidence_import_receipts"
            ),
            present=False,
        ),
    )
    payload["receipt_row_count"] = 0

    with pytest.raises(ValueError):
        SQLiteTrustedStoreRawSnapshot(**payload)


def test_snapshot_accepts_absent_receipt_table_without_facts():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteTablePresence,
    )

    payload = _valid_manual_snapshot_payload()
    payload["required_tables"] = (
        payload["required_tables"][0],
        SQLiteTablePresence(
            table_name=(
                "execution_evidence_import_receipts"
            ),
            present=False,
        ),
    )
    payload["receipt_row_count"] = None

    snapshot = SQLiteTrustedStoreRawSnapshot(
        **payload
    )

    assert snapshot.receipt_row_count is None
    assert snapshot.receipts == ()
    assert snapshot.receipts_read_error is None


def test_snapshot_rejects_out_of_order_malformed_rows():
    from execution_evidence.sqlite_trusted_store_snapshot import (
        SQLiteUnparseableTrustedReceiptRow,
    )

    payload = _valid_manual_snapshot_payload()
    payload.update(
        {
            "receipt_row_count": 2,
            "unparseable_receipt_rows": (
                SQLiteUnparseableTrustedReceiptRow(
                    receipt_rowid=20,
                    snapshot_row_index=1,
                    receipt_id="later",
                    error_type="ValidationError",
                ),
                SQLiteUnparseableTrustedReceiptRow(
                    receipt_rowid=10,
                    snapshot_row_index=0,
                    receipt_id="earlier",
                    error_type="ValidationError",
                ),
            ),
        }
    )

    with pytest.raises(ValueError):
        SQLiteTrustedStoreRawSnapshot(**payload)
