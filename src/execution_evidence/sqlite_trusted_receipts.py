from __future__ import annotations

import sqlite3
from typing import Literal


TrustedReceiptRowOrder = Literal[
    "lineage",
    "newest_first",
]


TRUSTED_RECEIPT_COLUMN_PROJECTION = """
    rowid AS receipt_rowid,
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
"""


TRUSTED_RECEIPT_LINEAGE_ORDER_SQL = f"""
SELECT
    {TRUSTED_RECEIPT_COLUMN_PROJECTION}
FROM execution_evidence_import_receipts
ORDER BY created_at, receipt_id
"""


TRUSTED_RECEIPT_NEWEST_FIRST_SQL = f"""
SELECT
    {TRUSTED_RECEIPT_COLUMN_PROJECTION}
FROM execution_evidence_import_receipts
ORDER BY created_at DESC, receipt_id
"""


def load_trusted_receipt_rows_from_connection(
    connection: sqlite3.Connection,
    *,
    order: TrustedReceiptRowOrder = "lineage",
) -> tuple[sqlite3.Row, ...]:
    """Load raw receipt rows from a caller-owned snapshot."""
    if not connection.in_transaction:
        raise ValueError(
            "Trusted receipt rows require an active "
            "caller-owned transaction."
        )

    if order == "lineage":
        statement = (
            TRUSTED_RECEIPT_LINEAGE_ORDER_SQL
        )
    elif order == "newest_first":
        statement = (
            TRUSTED_RECEIPT_NEWEST_FIRST_SQL
        )
    else:
        raise ValueError(
            f"Unsupported trusted receipt row order: "
            f"{order!r}."
        )

    cursor = connection.cursor()
    cursor.row_factory = sqlite3.Row

    try:
        rows = cursor.execute(
            statement
        ).fetchall()
    finally:
        cursor.close()

    return tuple(rows)
