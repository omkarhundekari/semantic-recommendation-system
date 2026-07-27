from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from execution_evidence.sqlite_trusted_receipts import (
    load_trusted_receipt_rows_from_connection,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)


def test_raw_receipt_rows_require_active_transaction(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
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
            load_trusted_receipt_rows_from_connection(
                connection
            )
    finally:
        connection.close()


def test_raw_receipt_rows_preserve_caller_ownership(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    receipt = initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )
    original_row_factory = lambda cursor, row: row
    connection.row_factory = original_row_factory

    try:
        connection.execute("BEGIN")

        rows = load_trusted_receipt_rows_from_connection(
            connection
        )

        assert len(rows) == 1
        assert rows[0]["receipt_rowid"] >= 1
        assert rows[0]["receipt_id"] == receipt.receipt_id
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


def test_raw_receipt_rows_reject_unknown_order(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-07-13T12:00:00+00:00",
    )

    connection = sqlite3.connect(
        str(database_path),
        isolation_level=None,
    )

    try:
        connection.execute("BEGIN")

        with pytest.raises(
            ValueError,
            match="Unsupported trusted receipt row order",
        ):
            load_trusted_receipt_rows_from_connection(
                connection,
                order="invalid",  # type: ignore[arg-type]
            )

        assert connection.in_transaction is True
    finally:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        connection.close()
