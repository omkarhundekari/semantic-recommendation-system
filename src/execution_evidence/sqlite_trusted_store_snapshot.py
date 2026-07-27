from __future__ import annotations

import sqlite3
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    model_validator,
)

from execution_evidence.sqlite_trusted_receipts import (
    load_trusted_receipt_rows_from_connection,
)
from execution_evidence.store_migration import (
    RepositoryEvidenceMigrationReceipt,
    deserialize_repository_evidence_migration_receipt,
)


SQLITE_TRUSTED_STORE_SNAPSHOT_FORMAT_VERSION = 1

TRUSTED_STORE_REQUIRED_TABLES = (
    "execution_evidence_schema_migrations",
    "execution_evidence_import_receipts",
)


class SQLiteSnapshotReadError(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    operation: str
    error_type: str
    message: str
    sqlite_errorcode: Optional[int] = None
    sqlite_errorname: Optional[str] = None


class SQLiteTablePresence(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    table_name: str
    present: bool


class SQLiteForeignKeyViolation(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    table: str
    rowid: Optional[int]
    parent: str
    foreign_key_index: int


class SQLiteUnparseableTrustedReceiptRow(
    BaseModel
):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    # Diagnostic-only physical location. This must
    # never become part of durable store identity.
    receipt_rowid: int

    # Index in the raw SQL enumeration order. Receipt
    # lineage authority comes only from predecessor IDs.
    snapshot_row_index: int

    receipt_id: Optional[str]
    error_type: str


class SQLiteTrustedStoreRawSnapshot(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    snapshot_format_version: Literal[1] = (
        SQLITE_TRUSTED_STORE_SNAPSHOT_FORMAT_VERSION
    )

    required_tables: tuple[
        SQLiteTablePresence,
        ...,
    ]

    schema_migration_version: Optional[int]
    schema_migration_version_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    user_version: Optional[int]
    user_version_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    data_version: Optional[int]
    data_version_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    integrity_messages: tuple[str, ...]
    integrity_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    foreign_key_violations: tuple[
        SQLiteForeignKeyViolation,
        ...,
    ]
    foreign_key_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    # None means rows could not be enumerated or the
    # receipt table was absent. Zero means the present
    # table was read successfully and was empty.
    receipt_row_count: Optional[int]

    receipts: tuple[
        RepositoryEvidenceMigrationReceipt,
        ...,
    ]
    unparseable_receipt_rows: tuple[
        SQLiteUnparseableTrustedReceiptRow,
        ...,
    ]
    receipts_read_error: (
        Optional[SQLiteSnapshotReadError]
    )

    @model_validator(mode="after")
    def _validate_snapshot(self):
        if self.receipts_read_error is not None:
            if self.receipt_row_count is not None:
                raise ValueError(
                    "Unreadable receipt state cannot expose "
                    "a completed receipt count."
                )

            if self.receipts:
                raise ValueError(
                    "Unreadable receipt state cannot expose "
                    "parsed receipts."
                )

            if self.unparseable_receipt_rows:
                raise ValueError(
                    "Unreadable receipt state cannot expose "
                    "malformed receipt observations."
                )

            return self

        if self.receipt_row_count is not None:
            observed = (
                len(self.receipts)
                + len(self.unparseable_receipt_rows)
            )

            if observed != self.receipt_row_count:
                raise ValueError(
                    "Receipt accounting mismatch."
                )

        return self


def _snapshot_read_error(
    operation: str,
    error: sqlite3.Error,
) -> SQLiteSnapshotReadError:
    return SQLiteSnapshotReadError(
        operation=operation,
        error_type=type(error).__name__,
        message=str(error),
        sqlite_errorcode=getattr(
            error,
            "sqlite_errorcode",
            None,
        ),
        sqlite_errorname=getattr(
            error,
            "sqlite_errorname",
            None,
        ),
    )


def _capture_required_tables(
    connection: sqlite3.Connection,
) -> tuple[SQLiteTablePresence, ...]:
    placeholders = ", ".join(
        "?"
        for _ in TRUSTED_STORE_REQUIRED_TABLES
    )

    rows = connection.execute(
        f"""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name IN ({placeholders})
        """,
        TRUSTED_STORE_REQUIRED_TABLES,
    ).fetchall()

    present_names = {
        str(row[0])
        for row in rows
    }

    return tuple(
        SQLiteTablePresence(
            table_name=table_name,
            present=table_name in present_names,
        )
        for table_name in TRUSTED_STORE_REQUIRED_TABLES
    )


def _table_is_present(
    table_presence: tuple[
        SQLiteTablePresence,
        ...,
    ],
    table_name: str,
) -> bool:
    return any(
        item.table_name == table_name
        and item.present
        for item in table_presence
    )


def capture_sqlite_trusted_store_snapshot(
    connection: sqlite3.Connection,
) -> SQLiteTrustedStoreRawSnapshot:
    """Capture replayable facts from one caller-owned transaction."""
    if not connection.in_transaction:
        raise ValueError(
            "Trusted-store snapshot capture requires "
            "an active caller-owned transaction."
        )

    original_row_factory = connection.row_factory

    try:
        connection.row_factory = sqlite3.Row

        # If sqlite_master itself cannot be read, there is
        # no trustworthy structural snapshot to return.
        required_tables = (
            _capture_required_tables(
                connection
            )
        )

        schema_migration_version = None
        schema_migration_version_read_error = None

        if _table_is_present(
            required_tables,
            "execution_evidence_schema_migrations",
        ):
            try:
                schema_row = connection.execute(
                    """
                    SELECT COALESCE(MAX(version), 0)
                        AS version
                    FROM execution_evidence_schema_migrations
                    """
                ).fetchone()
                schema_migration_version = (
                    int(schema_row["version"])
                    if schema_row is not None
                    else 0
                )
            except sqlite3.Error as error:
                schema_migration_version_read_error = (
                    _snapshot_read_error(
                        "read_schema_migration_version",
                        error,
                    )
                )

        user_version = None
        user_version_read_error = None
        try:
            row = connection.execute(
                "PRAGMA user_version"
            ).fetchone()
            user_version = (
                int(row[0])
                if row is not None
                else 0
            )
        except sqlite3.Error as error:
            user_version_read_error = (
                _snapshot_read_error(
                    "read_user_version",
                    error,
                )
            )

        data_version = None
        data_version_read_error = None
        try:
            row = connection.execute(
                "PRAGMA data_version"
            ).fetchone()
            data_version = (
                int(row[0])
                if row is not None
                else 0
            )
        except sqlite3.Error as error:
            data_version_read_error = (
                _snapshot_read_error(
                    "read_data_version",
                    error,
                )
            )

        integrity_messages: tuple[str, ...] = ()
        integrity_read_error = None
        try:
            rows = connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
            integrity_messages = tuple(
                str(row[0])
                for row in rows
            )
        except sqlite3.Error as error:
            integrity_read_error = (
                _snapshot_read_error(
                    "run_integrity_check",
                    error,
                )
            )

        foreign_key_violations: tuple[
            SQLiteForeignKeyViolation,
            ...,
        ] = ()
        foreign_key_read_error = None
        try:
            rows = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()
            foreign_key_violations = tuple(
                SQLiteForeignKeyViolation(
                    table=str(row[0]),
                    rowid=(
                        int(row[1])
                        if row[1] is not None
                        else None
                    ),
                    parent=str(row[2]),
                    foreign_key_index=int(row[3]),
                )
                for row in rows
            )
        except sqlite3.Error as error:
            foreign_key_read_error = (
                _snapshot_read_error(
                    "run_foreign_key_check",
                    error,
                )
            )

        receipt_row_count = None
        receipts = []
        unparseable_receipt_rows = []
        receipts_read_error = None

        if _table_is_present(
            required_tables,
            "execution_evidence_import_receipts",
        ):
            try:
                # Ordering is performed by SQLite over
                # raw values. NULL created_at values sort
                # deterministically before non-NULL values
                # in ascending order.
                receipt_rows = (
                    load_trusted_receipt_rows_from_connection(
                        connection,
                        order="lineage",
                    )
                )
                receipt_row_count = len(receipt_rows)

                for snapshot_row_index, row in enumerate(
                    receipt_rows
                ):
                    try:
                        receipts.append(
                            deserialize_repository_evidence_migration_receipt(
                                row
                            )
                        )
                    except (
                        ValidationError,
                        TypeError,
                        ValueError,
                    ) as error:
                        unparseable_receipt_rows.append(
                            SQLiteUnparseableTrustedReceiptRow(
                                receipt_rowid=int(
                                    row["receipt_rowid"]
                                ),
                                snapshot_row_index=(
                                    snapshot_row_index
                                ),
                                receipt_id=(
                                    str(row["receipt_id"])
                                    if row["receipt_id"]
                                    is not None
                                    else None
                                ),
                                error_type=(
                                    type(error).__name__
                                ),
                            )
                        )
            except sqlite3.Error as error:
                receipts_read_error = (
                    _snapshot_read_error(
                        "read_trusted_receipts",
                        error,
                    )
                )

        return SQLiteTrustedStoreRawSnapshot(
            required_tables=(
                required_tables
            ),
            schema_migration_version=(
                schema_migration_version
            ),
            schema_migration_version_read_error=(
                schema_migration_version_read_error
            ),
            user_version=user_version,
            user_version_read_error=(
                user_version_read_error
            ),
            data_version=data_version,
            data_version_read_error=(
                data_version_read_error
            ),
            integrity_messages=integrity_messages,
            integrity_read_error=(
                integrity_read_error
            ),
            foreign_key_violations=(
                foreign_key_violations
            ),
            foreign_key_read_error=(
                foreign_key_read_error
            ),
            receipt_row_count=receipt_row_count,
            receipts=tuple(receipts),
            unparseable_receipt_rows=tuple(
                unparseable_receipt_rows
            ),
            receipts_read_error=receipts_read_error,
        )
    finally:
        connection.row_factory = original_row_factory
