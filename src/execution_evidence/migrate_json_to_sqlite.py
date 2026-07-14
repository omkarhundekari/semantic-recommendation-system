from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from execution_evidence.store_migration import (
    RepositoryEvidenceMigrationError,
    dry_run_json_to_sqlite_migration,
    promote_json_to_sqlite_migration,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify or promote a JSON-to-SQLite "
            "execution evidence migration."
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
            "SQLite destination path. It and all "
            "SQLite sidecars must not already exist."
        ),
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        required=True,
        help="Path for the verified migration report.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help=(
            "Atomically promote the verified SQLite "
            "database. Without this flag, only a "
            "disposable dry run is performed."
        ),
    )
    parser.add_argument(
        "--allow-missing-empty-source",
        action="store_true",
        help=(
            "Treat a missing JSON source as an empty "
            "store. Intended only for development and "
            "explicit empty-store testing."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    try:
        if args.promote:
            report = (
                promote_json_to_sqlite_migration(
                    source_path=args.source_json,
                    destination_path=(
                        args.destination_db
                    ),
                    report_path=args.report_path,
                    created_at=created_at,
                    allow_missing_empty_source=(
                        args.allow_missing_empty_source
                    ),
                )
            )
            status = "promoted"
        else:
            report = (
                dry_run_json_to_sqlite_migration(
                    source_path=args.source_json,
                    destination_path=(
                        args.destination_db
                    ),
                    report_path=args.report_path,
                    created_at=created_at,
                    allow_missing_empty_source=(
                        args.allow_missing_empty_source
                    ),
                )
            )
            status = "verified"
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
                "status": status,
                "dry_run": report.dry_run,
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
                "destination_path": (
                    str(args.destination_db)
                    if args.promote
                    else None
                ),
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
