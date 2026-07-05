import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from planning.fixture_review_oracles import (
    FixtureReviewOracle,
    fixture_review_oracles,
)
from planning.manual_review_store import (
    DEFAULT_MANUAL_REVIEW_STORE,
    StoredManualReviewRecord,
    load_manual_review_records,
)


@dataclass(frozen=True)
class FixtureReviewOracleComparisonRow:
    fixture_id: str
    status: str
    artifact_id: Optional[str]
    review_id: Optional[str]
    reviewed_at_utc: Optional[str]
    expected_overall_preference: Optional[str]
    actual_overall_preference: Optional[str]
    expected_response_quality: Optional[str]
    actual_response_quality: Optional[str]
    overall_preference_match: Optional[bool]
    response_quality_match: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _latest_reviews_by_fixture(
    records: Sequence[StoredManualReviewRecord],
) -> Dict[str, StoredManualReviewRecord]:
    latest: Dict[str, StoredManualReviewRecord] = {}

    for record in sorted(
        records,
        key=lambda item: (
            item.reviewed_at_utc,
            item.review_id,
        ),
    ):
        latest[record.fixture_id] = record

    return latest


def build_fixture_review_oracle_comparison(
    records: Sequence[StoredManualReviewRecord],
    oracles: Sequence[FixtureReviewOracle],
) -> Dict[str, Any]:
    latest_by_fixture = _latest_reviews_by_fixture(records)
    oracle_by_fixture = {
        oracle.fixture_id: oracle
        for oracle in oracles
    }

    rows: List[FixtureReviewOracleComparisonRow] = []

    for fixture_id in sorted(
        set(latest_by_fixture).union(oracle_by_fixture)
    ):
        record = latest_by_fixture.get(fixture_id)
        oracle = oracle_by_fixture.get(fixture_id)

        if oracle is None:
            rows.append(
                FixtureReviewOracleComparisonRow(
                    fixture_id=fixture_id,
                    status="missing_oracle",
                    artifact_id=record.artifact_id if record else None,
                    review_id=record.review_id if record else None,
                    reviewed_at_utc=(
                        record.reviewed_at_utc if record else None
                    ),
                    expected_overall_preference=None,
                    actual_overall_preference=(
                        record.review.overall_preference
                        if record
                        else None
                    ),
                    expected_response_quality=None,
                    actual_response_quality=(
                        record.review.response_quality
                        if record
                        else None
                    ),
                    overall_preference_match=None,
                    response_quality_match=None,
                )
            )
            continue

        oracle.validate()

        if record is None:
            rows.append(
                FixtureReviewOracleComparisonRow(
                    fixture_id=fixture_id,
                    status="missing_review",
                    artifact_id=None,
                    review_id=None,
                    reviewed_at_utc=None,
                    expected_overall_preference=(
                        oracle.expected_overall_preference
                    ),
                    actual_overall_preference=None,
                    expected_response_quality=(
                        oracle.expected_response_quality
                    ),
                    actual_response_quality=None,
                    overall_preference_match=None,
                    response_quality_match=None,
                )
            )
            continue

        preference_match = (
            record.review.overall_preference
            == oracle.expected_overall_preference
        )
        quality_match = (
            record.review.response_quality
            == oracle.expected_response_quality
        )

        rows.append(
            FixtureReviewOracleComparisonRow(
                fixture_id=fixture_id,
                status=(
                    "matched"
                    if preference_match and quality_match
                    else "mismatch"
                ),
                artifact_id=record.artifact_id,
                review_id=record.review_id,
                reviewed_at_utc=record.reviewed_at_utc,
                expected_overall_preference=(
                    oracle.expected_overall_preference
                ),
                actual_overall_preference=(
                    record.review.overall_preference
                ),
                expected_response_quality=(
                    oracle.expected_response_quality
                ),
                actual_response_quality=(
                    record.review.response_quality
                ),
                overall_preference_match=preference_match,
                response_quality_match=quality_match,
            )
        )

    status_counts = Counter(row.status for row in rows)

    return {
        "latest_review_fixture_count": len(latest_by_fixture),
        "oracle_fixture_count": len(oracle_by_fixture),
        "comparison_counts": dict(sorted(status_counts.items())),
        "rows": [row.to_dict() for row in rows],
    }


def render_fixture_review_oracle_comparison(
    comparison: Dict[str, Any],
) -> str:
    lines = [
        "Fixture Review Oracle Comparison",
        "=" * 32,
        (
            "Latest reviewed fixtures: "
            f"{comparison['latest_review_fixture_count']}"
        ),
        f"Oracle fixtures: {comparison['oracle_fixture_count']}",
        "",
        "Comparison counts:",
    ]

    for status, count in comparison["comparison_counts"].items():
        lines.append(f"  {status}: {count}")

    lines.extend(["", "Fixture results:"])

    for row in comparison["rows"]:
        lines.append(
            "  "
            f"{row['fixture_id']} | {row['status']} | "
            f"expected={row['expected_overall_preference']} / "
            f"{row['expected_response_quality']} | "
            f"actual={row['actual_overall_preference']} / "
            f"{row['actual_response_quality']}"
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare latest manual fixture reviews to separate fixture oracles."
        )
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

    comparison = build_fixture_review_oracle_comparison(
        records=load_manual_review_records(args.store_path),
        oracles=fixture_review_oracles(),
    )

    if args.json:
        print(json.dumps(comparison, indent=2))
    else:
        print(render_fixture_review_oracle_comparison(comparison))


if __name__ == "__main__":
    main()
