import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from planning.fixture_review_oracle_comparison import (
    build_fixture_review_oracle_comparison,
)
from planning.fixture_review_oracles import fixture_review_oracles
from planning.manual_review_annotations import (
    DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE,
    load_manual_review_annotations,
)
from planning.manual_review_store import (
    DEFAULT_MANUAL_REVIEW_STORE,
    StoredManualReviewRecord,
    load_manual_review_records,
)
from planning.shadow_fixture_registry import fixture_cases


DEFAULT_ARTIFACT_DIR = Path("data/manual_fixture_artifacts")
DEFAULT_REPORT_DIR = Path("outputs/reports")
MIN_FIXTURES_FOR_CALIBRATION = 15


@dataclass(frozen=True)
class QualityWarningSummary:
    fixture_id: str
    artifact_id: str
    warning_code: str
    message: str
    candidate_titles: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelevanceTraceSummary:
    fixture_id: str
    artifact_id: str
    candidate_title: str
    source_id: str
    source_title: str
    support_scope: str
    relevance_status: str
    was_flagged: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FixtureReviewStatus:
    fixture_id: str
    artifact_id: Optional[str]
    review_completed: bool
    review_outcome: Optional[str]
    response_quality: Optional[str]
    oracle_status: Optional[str]
    oracle_matched: Optional[bool]
    reviewer_confidence: Optional[str]
    both_weak_diagnosis: Optional[str]
    relevance_trace_assessment: Optional[str]
    has_quality_warnings: bool
    has_suspicious_relevance: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _load_artifacts_by_id(
    artifact_dir: Path,
) -> Dict[str, Dict[str, Any]]:
    artifacts = {}

    for path in sorted(artifact_dir.glob("*/*.json")):
        artifact = json.loads(path.read_text())
        artifact_id = artifact["artifact_identity"]["artifact_id"]
        artifacts[artifact_id] = {
            "path": str(path),
            "artifact": artifact,
        }

    return artifacts


def _latest_records_by_fixture(
    records: Sequence[StoredManualReviewRecord],
) -> Dict[str, StoredManualReviewRecord]:
    latest = {}

    for record in sorted(
        records,
        key=lambda item: (
            item.reviewed_at_utc,
            item.review_id,
        ),
    ):
        latest[record.fixture_id] = record

    return latest


def _candidate_titles_from_warning(
    warning: Dict[str, Any],
) -> List[str]:
    candidates = warning.get("details", {}).get("candidates", [])

    return [
        candidate.get("candidate_title", "")
        for candidate in candidates
        if isinstance(candidate, dict)
        and candidate.get("candidate_title")
    ]


def _source_title_lookup(
    artifact: Dict[str, Any],
) -> Dict[str, str]:
    brief = artifact["v2_shadow"]["report"]["evidence_brief"]

    return {
        source["source_id"]: source["title"]
        for source in brief["sources"]
    }


def build_shadow_reviewer_report(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    review_store_path: Path = DEFAULT_MANUAL_REVIEW_STORE,
    annotation_store_path: Path = DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE,
) -> Dict[str, Any]:
    records = load_manual_review_records(review_store_path)
    annotations = load_manual_review_annotations(annotation_store_path)
    annotations_by_review_id = {
        annotation.review_id: annotation
        for annotation in annotations
    }
    artifacts_by_id = _load_artifacts_by_id(artifact_dir)
    latest_by_fixture = _latest_records_by_fixture(records)

    oracle_comparison = build_fixture_review_oracle_comparison(
        records=records,
        oracles=fixture_review_oracles(),
    )
    oracle_by_fixture = {
        row["fixture_id"]: row
        for row in oracle_comparison["rows"]
    }

    fixture_ids = [
        case.case_id
        for case in fixture_cases()
    ]

    latest_artifact_payloads = {}

    for fixture_id, record in latest_by_fixture.items():
        payload = artifacts_by_id.get(record.artifact_id)

        if payload is not None:
            latest_artifact_payloads[fixture_id] = payload["artifact"]

    outcome_distribution = Counter(
        (
            f"{record.review.overall_preference}/"
            f"{record.review.response_quality}"
        )
        for record in latest_by_fixture.values()
    )
    latest_annotations = [
        annotations_by_review_id[record.review_id]
        for record in latest_by_fixture.values()
        if record.review_id in annotations_by_review_id
    ]
    reviewer_confidence_counts = Counter(
        annotation.reviewer_confidence
        for annotation in latest_annotations
    )
    both_weak_diagnosis_counts = Counter(
        annotation.both_weak_diagnosis
        for annotation in latest_annotations
        if annotation.both_weak_diagnosis is not None
    )
    relevance_trace_assessment_counts = Counter(
        annotation.relevance_trace_assessment
        for annotation in latest_annotations
    )

    quality_warning_summary: List[QualityWarningSummary] = []
    relevance_trace_summary: List[RelevanceTraceSummary] = []

    for fixture_id, artifact in sorted(latest_artifact_payloads.items()):
        artifact_id = artifact["artifact_identity"]["artifact_id"]
        shadow = artifact["v2_shadow"]

        for warning in shadow.get("quality_warnings", {}).get(
            "warnings",
            [],
        ):
            quality_warning_summary.append(
                QualityWarningSummary(
                    fixture_id=fixture_id,
                    artifact_id=artifact_id,
                    warning_code=warning.get("code", ""),
                    message=warning.get("message", ""),
                    candidate_titles=_candidate_titles_from_warning(
                        warning
                    ),
                )
            )

        source_titles = _source_title_lookup(artifact)

        for trace in shadow.get("candidate_source_relevance", []):
            was_flagged = trace.get("relevance_status") in {
                "adjacent_context_only",
                "possible_mismatch",
                "invalid_source_id",
            }
            relevance_trace_summary.append(
                RelevanceTraceSummary(
                    fixture_id=fixture_id,
                    artifact_id=artifact_id,
                    candidate_title=trace.get("candidate_title", ""),
                    source_id=trace.get("source_id", ""),
                    source_title=source_titles.get(
                        trace.get("source_id", ""),
                        "",
                    ),
                    support_scope=trace.get("support_scope", ""),
                    relevance_status=trace.get("relevance_status", ""),
                    was_flagged=was_flagged,
                )
            )

    fixture_review_status = []

    for fixture_id in fixture_ids:
        record = latest_by_fixture.get(fixture_id)
        artifact = latest_artifact_payloads.get(fixture_id)
        oracle = oracle_by_fixture.get(fixture_id)
        annotation = (
            annotations_by_review_id.get(record.review_id)
            if record
            else None
        )

        warnings = (
            artifact.get("v2_shadow", {})
            .get("quality_warnings", {})
            .get("warnings", [])
            if artifact
            else []
        )
        relevance_traces = (
            artifact.get("v2_shadow", {})
            .get("candidate_source_relevance", [])
            if artifact
            else []
        )

        has_suspicious_relevance = any(
            trace.get("relevance_status")
            in {
                "adjacent_context_only",
                "possible_mismatch",
                "invalid_source_id",
            }
            for trace in relevance_traces
        )

        fixture_review_status.append(
            FixtureReviewStatus(
                fixture_id=fixture_id,
                artifact_id=record.artifact_id if record else None,
                review_completed=record is not None,
                review_outcome=(
                    record.review.overall_preference
                    if record
                    else None
                ),
                response_quality=(
                    record.review.response_quality
                    if record
                    else None
                ),
                oracle_status=oracle.get("status") if oracle else None,
                oracle_matched=(
                    (
                        oracle.get("overall_preference_match")
                        and oracle.get("response_quality_match")
                    )
                    if oracle
                    and oracle.get("overall_preference_match")
                    is not None
                    else None
                ),
                reviewer_confidence=(
                    annotation.reviewer_confidence
                    if annotation
                    else None
                ),
                both_weak_diagnosis=(
                    annotation.both_weak_diagnosis
                    if annotation
                    else None
                ),
                relevance_trace_assessment=(
                    annotation.relevance_trace_assessment
                    if annotation
                    else None
                ),
                has_quality_warnings=bool(warnings),
                has_suspicious_relevance=has_suspicious_relevance,
            )
        )

    reviewed_fixture_count = len(latest_by_fixture)

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rubric_version": "v1",
        "total_fixtures": len(fixture_ids),
        "reviewed_fixtures": reviewed_fixture_count,
        "unreviewed_fixtures": len(fixture_ids) - reviewed_fixture_count,
        "total_review_records": len(records),
        "review_annotation_count": len(annotations),
        "latest_review_annotation_count": len(latest_annotations),
        "total_artifact_files": len(artifacts_by_id),
        "data_sufficiency_warning": (
            "WARNING: This report covers "
            f"{reviewed_fixture_count} latest reviewed fixtures. "
            "Outcome distributions and warning rates are not yet stable. "
            "Do not use this report to derive thresholds or routing "
            "policies. Minimum recommended fixture count before "
            f"calibration: {MIN_FIXTURES_FOR_CALIBRATION}."
            if reviewed_fixture_count < MIN_FIXTURES_FOR_CALIBRATION
            else None
        ),
        "outcome_distribution": dict(
            sorted(outcome_distribution.items())
        ),
        "oracle_comparison_counts": dict(
            sorted(oracle_comparison["comparison_counts"].items())
        ),
        "reviewer_confidence_counts": dict(
            sorted(reviewer_confidence_counts.items())
        ),
        "both_weak_diagnosis_counts": dict(
            sorted(both_weak_diagnosis_counts.items())
        ),
        "relevance_trace_assessment_counts": dict(
            sorted(relevance_trace_assessment_counts.items())
        ),
        "quality_warning_summary": [
            row.to_dict()
            for row in quality_warning_summary
        ],
        "relevance_trace_summary": [
            row.to_dict()
            for row in relevance_trace_summary
        ],
        "fixture_review_status": [
            row.to_dict()
            for row in fixture_review_status
        ],
    }


def render_shadow_reviewer_report(
    report: Dict[str, Any],
) -> str:
    lines = [
        "# Shadow Reviewer Report",
        "",
        f"Generated at: `{report['generated_at_utc']}`",
        f"Rubric version: `{report['rubric_version']}`",
        "",
    ]

    if report["data_sufficiency_warning"]:
        lines.extend(
            [
                "## Data Sufficiency Warning",
                "",
                report["data_sufficiency_warning"],
                "",
            ]
        )

    lines.extend(
        [
            "## Overview",
            "",
            f"- Total fixture cases: {report['total_fixtures']}",
            f"- Reviewed fixtures: {report['reviewed_fixtures']}",
            f"- Unreviewed fixtures: {report['unreviewed_fixtures']}",
            f"- Review records: {report['total_review_records']}",
            f"- Review annotations: {report['review_annotation_count']}",
            f"- Latest review annotations: {report['latest_review_annotation_count']}",
            f"- Artifact files: {report['total_artifact_files']}",
            "",
            "## Outcome Distribution",
            "",
        ]
    )

    if report["outcome_distribution"]:
        for outcome, count in report["outcome_distribution"].items():
            lines.append(f"- `{outcome}`: {count}")
    else:
        lines.append("- No reviewed outcomes yet.")

    lines.extend(
        [
            "",
            "## Oracle Comparison Summary",
            "",
        ]
    )

    if report["oracle_comparison_counts"]:
        for status, count in report["oracle_comparison_counts"].items():
            lines.append(f"- `{status}`: {count}")
    else:
        lines.append("- No oracle comparisons yet.")

    lines.extend(
        [
            "",
            "## Review Annotation Summary",
            "",
            "Reviewer confidence:",
        ]
    )

    if report["reviewer_confidence_counts"]:
        for key, count in report["reviewer_confidence_counts"].items():
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- No latest review annotations yet.")

    lines.append("")
    lines.append("Both-weak diagnosis:")

    if report["both_weak_diagnosis_counts"]:
        for key, count in report["both_weak_diagnosis_counts"].items():
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- No both-weak diagnosis annotations.")

    lines.append("")
    lines.append("Relevance trace assessment:")

    if report["relevance_trace_assessment_counts"]:
        for key, count in report["relevance_trace_assessment_counts"].items():
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- No relevance trace annotations yet.")

    lines.extend(
        [
            "",
            "## Quality Warnings Needing Attention",
            "",
        ]
    )

    if report["quality_warning_summary"]:
        for warning in report["quality_warning_summary"]:
            candidates = ", ".join(
                warning["candidate_titles"]
            ) or "n/a"
            lines.extend(
                [
                    f"### {warning['fixture_id']}",
                    f"- Artifact: `{warning['artifact_id']}`",
                    f"- Warning: `{warning['warning_code']}`",
                    f"- Candidates: {candidates}",
                    f"- Message: {warning['message']}",
                    "",
                ]
            )
    else:
        lines.append("No quality warnings in latest reviewed artifacts.")
        lines.append("")

    lines.extend(
        [
            "## Suspicious Candidate-to-Source Relevance Traces",
            "",
        ]
    )

    suspicious = [
        trace
        for trace in report["relevance_trace_summary"]
        if trace["was_flagged"]
    ]

    if suspicious:
        for trace in suspicious:
            lines.extend(
                [
                    f"### {trace['fixture_id']}",
                    f"- Artifact: `{trace['artifact_id']}`",
                    f"- Candidate: {trace['candidate_title']}",
                    (
                        f"- Source: `{trace['source_id']}` "
                        f"{trace['source_title']}"
                    ),
                    f"- Support scope: `{trace['support_scope']}`",
                    f"- Relevance status: `{trace['relevance_status']}`",
                    "",
                ]
            )
    else:
        lines.append("No suspicious relevance traces in latest reviewed artifacts.")
        lines.append("")

    lines.extend(
        [
            "## Fixture Review Status",
            "",
            "| Fixture | Reviewed | Latest artifact | Outcome | Quality | Oracle | Confidence | Both-weak diagnosis | Relevance assessment | Warnings | Suspicious relevance |",
            "|---|---:|---|---|---|---|---|---|---|---:|---:|",
        ]
    )

    for row in report["fixture_review_status"]:
        artifact_cell = (
            f"`{row['artifact_id']}`"
            if row["artifact_id"]
            else ""
        )
        lines.append(
            "| "
            f"{row['fixture_id']} | "
            f"{'yes' if row['review_completed'] else 'no'} | "
            f"{artifact_cell} | "
            f"{row['review_outcome'] or ''} | "
            f"{row['response_quality'] or ''} | "
            f"{row['oracle_status'] or ''} | "
            f"{row['reviewer_confidence'] or ''} | "
            f"{row['both_weak_diagnosis'] or ''} | "
            f"{row['relevance_trace_assessment'] or ''} | "
            f"{'yes' if row['has_quality_warnings'] else 'no'} | "
            f"{'yes' if row['has_suspicious_relevance'] else 'no'} |"
        )

    return "\n".join(lines) + "\n"


def write_shadow_reviewer_report(
    report: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = output_dir / "shadow_reviewer_report.md"
    json_path = output_dir / "shadow_reviewer_report.json"

    markdown_path.write_text(render_shadow_reviewer_report(report))
    json_path.write_text(json.dumps(report, indent=2))

    return {
        "markdown_path": markdown_path,
        "json_path": json_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a read-only shadow reviewer report."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_ARTIFACT_DIR,
    )
    parser.add_argument(
        "--review-store-path",
        type=Path,
        default=DEFAULT_MANUAL_REVIEW_STORE,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print report JSON to stdout instead of writing files.",
    )
    args = parser.parse_args()
    return args


def main() -> None:
    args = parse_args()
    report = build_shadow_reviewer_report(
        artifact_dir=args.artifact_dir,
        review_store_path=args.review_store_path,
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return

    written = write_shadow_reviewer_report(
        report=report,
        output_dir=args.output_dir,
    )

    print(f"Wrote Markdown report: {written['markdown_path']}")
    print(f"Wrote JSON report: {written['json_path']}")


if __name__ == "__main__":
    main()
