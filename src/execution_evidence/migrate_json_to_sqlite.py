from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from execution_evidence.store_migration import (
    RepositoryEvidenceMigrationError,
    dry_run_json_to_sqlite_migration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a JSON-to-SQLite execution "
            "evidence migration without promoting "
            "the SQLite database."
        )
    )
    parser.add_argument(
        "--source-json",
        type=Path,
        required=True,
        help="Path to the current JSON evidence store.",
    )
    parser.add_argument(
        "--destination-db",
        type=Path,
        required=True,
        help=(
            "Future SQLite destination path. "
            "It must not already exist."
        ),
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        required=True,
        help="Path for the verified dry-run report.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        report = (
            dry_run_json_to_sqlite_migration(
                source_path=args.source_json,
                destination_path=(
                    args.destination_db
                ),
                report_path=args.report_path,
                created_at=created_at,
            )
        )
    except RepositoryEvidenceMigrationError as error:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "verified",
                "dry_run": True,
                "repository_count": (
                    report.repository_count
                ),
                "evidence_count": (
                    report.evidence_count
                ),
                "attribution_count": (
                    report.attribution_count
                ),
                "root_hash": report.root_hash,
                "report_path": str(
                    args.report_path
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
