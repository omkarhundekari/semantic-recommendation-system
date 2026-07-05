import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from planning.manual_review_store import (
    DEFAULT_MANUAL_REVIEW_STORE,
    StoredManualReviewRecord,
    load_manual_review_records,
)


@dataclass(frozen=True)
class ManualReviewSummaryRow:
    fixture_id: str
    artifact_id: str
    review_id: str
    reviewer_id: str
    reviewed_at_utc: str
    overall_preference: str
    response_quality: str
    is_latest_for_fixture: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_manual_review_summary(
    records: Sequence[StoredManualReviewRecord],
) -> Dict[str, Any]:
    ordered_records = sorted(
        records,
        key=lambda record: (
            record.reviewed_at_utc,
            record.review_id,
        ),
    )

    latest_by_fixture = {}
    for record in ordered_records:
        latest_by_fixture[record.fixture_id] = record.review_id

    rows = [
        ManualReviewSummaryRow(
            fixture_id=record.fixture_id,
            artifact_id=record.artifact_id,
            review_id=record.review_id,
            reviewer_id=record.reviewer_id,
            reviewed_at_utc=record.reviewed_at_utc,
            overall_preference=record.review.overall_preference,
            response_quality=record.review.response_quality,
            is_latest_for_fixture=(
                latest_by_fixture[record.fixture_id] == record.review_id
            ),
        )
        for record in ordered_records
    ]

    preference_counts = Counter(
        row.overall_preference
        for row in rows
    )
    response_quality_counts = Counter(
        row.response_quality
        for row in rows
    )

    latest_rows = [
        row
        for row in rows
        if row.is_latest_for_fixture
    ]

    return {
        "review_record_count": len(rows),
        "fixture_count": len(latest_by_fixture),
        "preference_counts": dict(sorted(preference_counts.items())),
        "response_quality_counts": dict(
            sorted(response_quality_counts.items())
        ),
        "artifact_reviews": [
            row.to_dict()
            for row in rows
        ],
        "latest_review_by_fixture": [
            row.to_dict()
            for row in latest_rows
        ],
    }


def render_manual_review_summary(
    summary: Dict[str, Any],
) -> str:
    lines = [
        "Manual Planner Review Summary",
        "=" * 30,
        f"Review records: {summary['review_record_count']}",
        f"Fixtures: {summary['fixture_count']}",
        "",
        "Overall preference counts:",
    ]

    for key, count in summary["preference_counts"].items():
        lines.append(f"  {key}: {count}")

    lines.extend(
        [
            "",
            "Response quality counts:",
        ]
    )

    for key, count in summary["response_quality_counts"].items():
        lines.append(f"  {key}: {count}")

    lines.extend(
        [
            "",
            "Artifact review records:",
        ]
    )

    for row in summary["artifact_reviews"]:
        latest_marker = " latest-for-fixture" if row[
            "is_latest_for_fixture"
        ] else ""
        lines.append(
            "  "
            f"{row['fixture_id']} | "
            f"{row['artifact_id']} | "
            f"{row['overall_preference']} / "
            f"{row['response_quality']} | "
            f"{row['reviewed_at_utc']}{latest_marker}"
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize append-only manual planner reviews."
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=DEFAULT_MANUAL_REVIEW_STORE,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of text.",
    )
    args = parser.parse_args()

    records = load_manual_review_records(args.store_path)
    summary = build_manual_review_summary(records)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_manual_review_summary(summary))


if __name__ == "__main__":
    main()
