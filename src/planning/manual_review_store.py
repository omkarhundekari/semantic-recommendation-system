import json
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning.manual_review_rubric import (
    ManualCandidateReview,
    ManualReviewRecord,
    ManualSetReview,
)
from planning.shadow_fixture_registry import fixture_cases


DEFAULT_MANUAL_REVIEW_STORE = Path(
    "data/manual_planner_reviews_v1.jsonl"
)

_HEX_32_PATTERN = re.compile(r"^[a-f0-9]{32}$")
_HEX_64_PATTERN = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class StoredManualReviewRecord:
    """
    Immutable, append-only review entry.

    The nested review contains the rubric scores. Top-level metadata links the
    review to one exact generated artifact without embedding the review in an
    artifact that may be regenerated later.
    """

    review_id: str
    artifact_id: str
    fixture_id: str
    artifact_path_hint: str
    prompt_content_hash: str
    reviewer_id: str
    reviewed_at_utc: str
    review: ManualReviewRecord
    supersedes: Optional[str] = None
    schema_version: str = "v1"

    def validate(self) -> None:
        if self.schema_version != "v1":
            raise ValueError("Unsupported manual review store schema version.")

        if not _HEX_32_PATTERN.fullmatch(self.review_id):
            raise ValueError("review_id must be a 32-character lowercase hex ID.")

        if not _HEX_32_PATTERN.fullmatch(self.artifact_id):
            raise ValueError(
                "artifact_id must be a 32-character lowercase hex ID."
            )

        if self.supersedes is not None and not _HEX_32_PATTERN.fullmatch(
            self.supersedes
        ):
            raise ValueError(
                "supersedes must be a 32-character lowercase hex ID or None."
            )

        known_fixture_ids = {
            fixture.case_id
            for fixture in fixture_cases()
        }

        if self.fixture_id not in known_fixture_ids:
            raise ValueError(
                f"Unknown fixture ID in manual review: {self.fixture_id}"
            )

        if not self.artifact_path_hint.strip():
            raise ValueError("artifact_path_hint must be non-empty.")

        if not _HEX_64_PATTERN.fullmatch(self.prompt_content_hash):
            raise ValueError(
                "prompt_content_hash must be a 64-character lowercase hex hash."
            )

        if not self.reviewer_id.strip():
            raise ValueError("reviewer_id must be non-empty.")

        try:
            datetime.strptime(
                self.reviewed_at_utc,
                "%Y%m%dT%H%M%SZ",
            )
        except ValueError as error:
            raise ValueError(
                "reviewed_at_utc must use YYYYMMDDTHHMMSSZ format."
            ) from error

        self.review.validate()
        _validate_completed_review(self.review)

    def to_dict(self) -> Dict[str, Any]:
        self.validate()

        return {
            "schema_version": self.schema_version,
            "review_id": self.review_id,
            "artifact_id": self.artifact_id,
            "fixture_id": self.fixture_id,
            "artifact_path_hint": self.artifact_path_hint,
            "prompt_content_hash": self.prompt_content_hash,
            "reviewer_id": self.reviewer_id,
            "reviewed_at_utc": self.reviewed_at_utc,
            "rubric_version": self.review.rubric_version,
            "supersedes": self.supersedes,
            "review": self.review.to_dict(),
        }


def _validate_completed_review(review: ManualReviewRecord) -> None:
    for set_review in (
        review.deterministic_review,
        review.openai_review,
    ):
        if not set_review.candidate_reviews:
            raise ValueError(
                "Completed review requires candidate scores for both planners."
            )

        if set_review.distinctiveness is None:
            raise ValueError(
                "Completed review requires set-level distinctiveness scores."
            )

        for candidate_review in set_review.candidate_reviews:
            if any(
                score is None
                for score in (
                    candidate_review.goal_alignment,
                    candidate_review.grounding,
                    candidate_review.scope_realism,
                )
            ):
                raise ValueError(
                    "Completed review requires all candidate rubric scores."
                )

    if review.overall_preference is None:
        raise ValueError(
            "Completed review requires an overall preference."
        )

    if review.response_quality is None:
        raise ValueError(
            "Completed review requires a response-quality assessment."
        )

    if review.unique_angle_quality is None:
        raise ValueError(
            "Completed review requires a unique-angle assessment."
        )


def _candidate_reviews_from_dict(
    payload: List[Dict[str, Any]],
) -> List[ManualCandidateReview]:
    return [
        ManualCandidateReview(
            candidate_title=str(item.get("candidate_title", "")),
            goal_alignment=item.get("goal_alignment"),
            grounding=item.get("grounding"),
            scope_realism=item.get("scope_realism"),
            notes=str(item.get("notes", "")),
        )
        for item in payload
        if isinstance(item, dict)
    ]


def _set_review_from_dict(
    payload: Dict[str, Any],
) -> ManualSetReview:
    return ManualSetReview(
        planner_path=str(payload.get("planner_path", "")),
        candidate_reviews=_candidate_reviews_from_dict(
            payload.get("candidate_reviews", [])
        ),
        distinctiveness=payload.get("distinctiveness"),
        notes=str(payload.get("notes", "")),
    )


def _review_from_dict(payload: Dict[str, Any]) -> ManualReviewRecord:
    return ManualReviewRecord(
        rubric_version=str(payload.get("rubric_version", "")),
        query_fingerprint=str(payload.get("query_fingerprint", "")),
        deterministic_review=_set_review_from_dict(
            dict(payload.get("deterministic_review", {}))
        ),
        openai_review=_set_review_from_dict(
            dict(payload.get("openai_review", {}))
        ),
        overall_preference=payload.get("overall_preference"),
        overall_preference_reason=str(
            payload.get("overall_preference_reason", "")
        ),
        response_quality=payload.get("response_quality"),
        response_quality_reason=str(
            payload.get("response_quality_reason", "")
        ),
        unique_angle_quality=payload.get("unique_angle_quality"),
        unique_angle_quality_reason=str(
            payload.get("unique_angle_quality_reason", "")
        ),
        reviewer_notes=str(payload.get("reviewer_notes", "")),
    )


def stored_review_from_dict(
    payload: Dict[str, Any],
) -> StoredManualReviewRecord:
    review_payload = payload.get("review")

    if not isinstance(review_payload, dict):
        raise ValueError("Stored review record must contain a review payload.")

    record = StoredManualReviewRecord(
        schema_version=str(payload.get("schema_version", "")),
        review_id=str(payload.get("review_id", "")),
        artifact_id=str(payload.get("artifact_id", "")),
        fixture_id=str(payload.get("fixture_id", "")),
        artifact_path_hint=str(payload.get("artifact_path_hint", "")),
        prompt_content_hash=str(
            payload.get("prompt_content_hash", "")
        ),
        reviewer_id=str(payload.get("reviewer_id", "")),
        reviewed_at_utc=str(payload.get("reviewed_at_utc", "")),
        supersedes=payload.get("supersedes"),
        review=_review_from_dict(review_payload),
    )
    record.validate()
    return record


def build_stored_manual_review_record(
    artifact: Dict[str, Any],
    review: ManualReviewRecord,
    reviewer_id: str,
    artifact_path_hint: str,
    review_id: Optional[str] = None,
    reviewed_at_utc: Optional[str] = None,
    supersedes: Optional[str] = None,
) -> StoredManualReviewRecord:
    identity = artifact.get("artifact_identity", {})
    shadow = artifact.get("v2_shadow", {})
    template = shadow.get("manual_review_template", {})
    metadata = shadow.get("generation_metadata", {})

    artifact_id = str(identity.get("artifact_id", ""))
    fixture_id = str(identity.get("fixture_id", ""))
    prompt_content_hash = str(
        metadata.get("prompt_content_hash", "")
    )

    if not isinstance(template, dict):
        raise ValueError(
            "Artifact must contain a manual review template."
        )

    if review.rubric_version != str(
        template.get("rubric_version", "")
    ):
        raise ValueError(
            "Review rubric version must match the artifact template."
        )

    if review.query_fingerprint != str(
        template.get("query_fingerprint", "")
    ):
        raise ValueError(
            "Review query fingerprint must match the artifact template."
        )

    _validate_template_titles(
        review=review,
        template=template,
    )

    return StoredManualReviewRecord(
        review_id=review_id or uuid.uuid4().hex,
        artifact_id=artifact_id,
        fixture_id=fixture_id,
        artifact_path_hint=artifact_path_hint,
        prompt_content_hash=prompt_content_hash,
        reviewer_id=reviewer_id,
        reviewed_at_utc=reviewed_at_utc or datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ"),
        review=review,
        supersedes=supersedes,
    )


def _validate_template_titles(
    review: ManualReviewRecord,
    template: Dict[str, Any],
) -> None:
    expected = {
        "deterministic": [
            str(item.get("candidate_title", "")).strip()
            for item in template.get(
                "deterministic_review",
                {},
            ).get("candidate_reviews", [])
            if str(item.get("candidate_title", "")).strip()
        ],
        "openai": [
            str(item.get("candidate_title", "")).strip()
            for item in template.get(
                "openai_review",
                {},
            ).get("candidate_reviews", [])
            if str(item.get("candidate_title", "")).strip()
        ],
    }

    observed = {
        "deterministic": [
            item.candidate_title.strip()
            for item in review.deterministic_review.candidate_reviews
        ],
        "openai": [
            item.candidate_title.strip()
            for item in review.openai_review.candidate_reviews
        ],
    }

    if observed != expected:
        raise ValueError(
            "Review candidate titles must match the artifact template."
        )


def load_manual_review_records(
    path: Path = DEFAULT_MANUAL_REVIEW_STORE,
) -> List[StoredManualReviewRecord]:
    if not path.exists():
        return []

    records = []

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
                f"Invalid JSONL review record at line {line_number}."
            ) from error

        records.append(stored_review_from_dict(payload))

    return records


def append_manual_review_record(
    record: StoredManualReviewRecord,
    path: Path = DEFAULT_MANUAL_REVIEW_STORE,
) -> Path:
    record.validate()

    existing_ids = {
        item.review_id
        for item in load_manual_review_records(path)
    }

    if record.review_id in existing_ids:
        raise ValueError(
            f"Review ID already exists in append-only store: {record.review_id}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict()) + "\n")

    return path
