import argparse
import json
import re
import uuid
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from planning.shadow_fixture_registry import fixture_cases


DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE = Path(
    "data/manual_review_annotations_v1.jsonl"
)

_HEX_32_PATTERN = re.compile(r"^[0-9a-f]{32}$")

REVIEWER_CONFIDENCE_OPTIONS = {
    "high",
    "medium",
    "low",
}

BOTH_WEAK_DIAGNOSIS_OPTIONS = {
    "evidence_sparse",
    "deterministic_template_failure",
    "shadow_drift_without_grounding",
    "query_underspecified",
    "unknown",
}

RELEVANCE_TRACE_ASSESSMENT_OPTIONS = {
    "traces_match_reviewer_judgment",
    "traces_over_flagging",
    "traces_under_flagging",
    "not_assessed",
}


@dataclass(frozen=True)
class ManualReviewAnnotation:
    schema_version: str
    annotation_id: str
    review_id: str
    artifact_id: str
    fixture_id: str
    annotator_id: str
    annotated_at_utc: str
    packet_generator_version: str
    reviewer_confidence: str
    reviewer_confidence_reason: str
    both_weak_diagnosis: Optional[str]
    both_weak_diagnosis_reason: Optional[str]
    relevance_trace_assessment: str
    relevance_trace_assessment_notes: str

    def validate(self) -> None:
        if self.schema_version != "v1":
            raise ValueError("Manual review annotation schema_version must be v1.")

        if not _HEX_32_PATTERN.fullmatch(self.annotation_id):
            raise ValueError(
                "annotation_id must be a 32-character lowercase hex ID."
            )

        if not _HEX_32_PATTERN.fullmatch(self.review_id):
            raise ValueError(
                "review_id must be a 32-character lowercase hex ID."
            )

        if not _HEX_32_PATTERN.fullmatch(self.artifact_id):
            raise ValueError(
                "artifact_id must be a 32-character lowercase hex ID."
            )

        known_fixture_ids = {
            fixture.case_id
            for fixture in fixture_cases()
        }

        if self.fixture_id not in known_fixture_ids:
            raise ValueError(
                f"Unknown fixture ID in review annotation: {self.fixture_id}"
            )

        if not self.annotator_id.strip():
            raise ValueError("annotator_id must be non-empty.")

        try:
            datetime.strptime(
                self.annotated_at_utc,
                "%Y%m%dT%H%M%SZ",
            )
        except ValueError as error:
            raise ValueError(
                "annotated_at_utc must use YYYYMMDDTHHMMSSZ format."
            ) from error

        if not self.packet_generator_version.strip():
            raise ValueError("packet_generator_version must be non-empty.")

        if self.reviewer_confidence not in REVIEWER_CONFIDENCE_OPTIONS:
            raise ValueError(
                "reviewer_confidence must be one of "
                f"{sorted(REVIEWER_CONFIDENCE_OPTIONS)}."
            )

        if (
            self.reviewer_confidence in {"medium", "low"}
            and not self.reviewer_confidence_reason.strip()
        ):
            raise ValueError(
                "reviewer_confidence_reason is required for medium or low confidence."
            )

        if self.both_weak_diagnosis is not None:
            if self.both_weak_diagnosis not in BOTH_WEAK_DIAGNOSIS_OPTIONS:
                raise ValueError(
                    "both_weak_diagnosis must be one of "
                    f"{sorted(BOTH_WEAK_DIAGNOSIS_OPTIONS)} or None."
                )

            if (
                self.both_weak_diagnosis != "unknown"
                and not str(self.both_weak_diagnosis_reason or "").strip()
            ):
                raise ValueError(
                    "both_weak_diagnosis_reason is required unless diagnosis is unknown."
                )

        if self.relevance_trace_assessment not in RELEVANCE_TRACE_ASSESSMENT_OPTIONS:
            raise ValueError(
                "relevance_trace_assessment must be one of "
                f"{sorted(RELEVANCE_TRACE_ASSESSMENT_OPTIONS)}."
            )

        if (
            self.relevance_trace_assessment
            in {"traces_over_flagging", "traces_under_flagging"}
            and not self.relevance_trace_assessment_notes.strip()
        ):
            raise ValueError(
                "relevance_trace_assessment_notes is required for trace disagreement."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


def build_manual_review_annotation(
    review_id: str,
    artifact_id: str,
    fixture_id: str,
    annotator_id: str,
    packet_generator_version: str,
    reviewer_confidence: str,
    reviewer_confidence_reason: str = "",
    both_weak_diagnosis: Optional[str] = None,
    both_weak_diagnosis_reason: Optional[str] = None,
    relevance_trace_assessment: str = "not_assessed",
    relevance_trace_assessment_notes: str = "",
    annotation_id: Optional[str] = None,
    annotated_at_utc: Optional[str] = None,
) -> ManualReviewAnnotation:
    annotation = ManualReviewAnnotation(
        schema_version="v1",
        annotation_id=annotation_id or uuid.uuid4().hex,
        review_id=review_id,
        artifact_id=artifact_id,
        fixture_id=fixture_id,
        annotator_id=annotator_id,
        annotated_at_utc=annotated_at_utc
        or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        packet_generator_version=packet_generator_version,
        reviewer_confidence=reviewer_confidence,
        reviewer_confidence_reason=reviewer_confidence_reason,
        both_weak_diagnosis=both_weak_diagnosis,
        both_weak_diagnosis_reason=both_weak_diagnosis_reason,
        relevance_trace_assessment=relevance_trace_assessment,
        relevance_trace_assessment_notes=relevance_trace_assessment_notes,
    )
    annotation.validate()
    return annotation


def manual_review_annotation_from_dict(
    payload: Dict[str, Any],
) -> ManualReviewAnnotation:
    annotation = ManualReviewAnnotation(
        schema_version=str(payload.get("schema_version", "")),
        annotation_id=str(payload.get("annotation_id", "")),
        review_id=str(payload.get("review_id", "")),
        artifact_id=str(payload.get("artifact_id", "")),
        fixture_id=str(payload.get("fixture_id", "")),
        annotator_id=str(payload.get("annotator_id", "")),
        annotated_at_utc=str(payload.get("annotated_at_utc", "")),
        packet_generator_version=str(
            payload.get("packet_generator_version", "")
        ),
        reviewer_confidence=str(payload.get("reviewer_confidence", "")),
        reviewer_confidence_reason=str(
            payload.get("reviewer_confidence_reason", "")
        ),
        both_weak_diagnosis=payload.get("both_weak_diagnosis"),
        both_weak_diagnosis_reason=payload.get(
            "both_weak_diagnosis_reason"
        ),
        relevance_trace_assessment=str(
            payload.get("relevance_trace_assessment", "")
        ),
        relevance_trace_assessment_notes=str(
            payload.get("relevance_trace_assessment_notes", "")
        ),
    )
    annotation.validate()
    return annotation


def load_manual_review_annotations(
    path: Path = DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE,
) -> List[ManualReviewAnnotation]:
    if not path.exists():
        return []

    annotations = []

    for line_number, line in enumerate(
        path.read_text().splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSONL annotation record at line {line_number}."
            ) from error

        annotations.append(manual_review_annotation_from_dict(payload))

    return annotations


def append_manual_review_annotation(
    annotation: ManualReviewAnnotation,
    path: Path = DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE,
) -> None:
    annotation.validate()

    existing = load_manual_review_annotations(path)
    existing_annotation_ids = {
        item.annotation_id
        for item in existing
    }
    existing_review_ids = {
        item.review_id
        for item in existing
    }

    if annotation.annotation_id in existing_annotation_ids:
        raise ValueError(
            f"Manual review annotation already exists: {annotation.annotation_id}"
        )

    if annotation.review_id in existing_review_ids:
        raise ValueError(
            f"Manual review already has an annotation: {annotation.review_id}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(annotation.to_dict(), sort_keys=True))
        handle.write("\n")


def build_manual_review_annotation_summary(
    annotations: Sequence[ManualReviewAnnotation],
) -> Dict[str, Any]:
    confidence_counts = Counter(
        annotation.reviewer_confidence
        for annotation in annotations
    )
    both_weak_counts = Counter(
        annotation.both_weak_diagnosis
        for annotation in annotations
        if annotation.both_weak_diagnosis is not None
    )
    relevance_counts = Counter(
        annotation.relevance_trace_assessment
        for annotation in annotations
    )

    return {
        "annotation_count": len(annotations),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "both_weak_diagnosis_counts": dict(sorted(both_weak_counts.items())),
        "relevance_trace_assessment_counts": dict(
            sorted(relevance_counts.items())
        ),
        "annotations": [
            annotation.to_dict()
            for annotation in annotations
        ],
    }


def render_manual_review_annotation_summary(
    summary: Dict[str, Any],
) -> str:
    lines = [
        "Manual Review Annotation Summary",
        "=" * 32,
        f"Annotations: {summary['annotation_count']}",
        "",
        "Reviewer confidence counts:",
    ]

    for key, count in summary["confidence_counts"].items():
        lines.append(f"  {key}: {count}")

    lines.extend(["", "Both-weak diagnosis counts:"])

    if summary["both_weak_diagnosis_counts"]:
        for key, count in summary["both_weak_diagnosis_counts"].items():
            lines.append(f"  {key}: {count}")
    else:
        lines.append("  none: 0")

    lines.extend(["", "Relevance trace assessment counts:"])

    for key, count in summary["relevance_trace_assessment_counts"].items():
        lines.append(f"  {key}: {count}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize append-only manual review annotations."
    )
    parser.add_argument(
        "--store-path",
        type=Path,
        default=DEFAULT_MANUAL_REVIEW_ANNOTATION_STORE,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of text.",
    )
    args = parser.parse_args()

    annotations = load_manual_review_annotations(args.store_path)
    summary = build_manual_review_annotation_summary(annotations)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_manual_review_annotation_summary(summary))


if __name__ == "__main__":
    main()
