from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence


SCORE_VALUES = {0, 1, 2}
PREFERENCE_OPTIONS = {
    "deterministic",
    "openai",
    "tie",
    "both_weak",
}
UNIQUE_ANGLE_QUALITY_OPTIONS = {
    "better",
    "equivalent",
    "worse",
    "not_applicable",
}
RESPONSE_QUALITY_OPTIONS = {
    "standard",
    "limited",
    "exploratory",
}


@dataclass(frozen=True)
class ManualReviewRubric:
    """
    Versioned instructions for offline comparison of deterministic and shadow
    planner outputs. Scores are intentionally manual; this contract does not
    automate subjective quality judgment.
    """

    version: str = "v1"

    goal_alignment_instruction: str = (
        "Read the user goal and the candidate title plus problem statement. "
        "Score 2 when the candidate directly addresses the specific goal, "
        "1 when it addresses an adjacent problem in the same domain, and "
        "0 when it is unrelated."
    )
    grounding_instruction: str = (
        "Read the candidate source IDs with the mapped evidence titles and "
        "excerpts. Score 2 when cited evidence clearly supports the "
        "direction, 1 when evidence is adjacent but not specific, and "
        "0 when citations are absent, invalid, or mismatched."
    )
    scope_realism_instruction: str = (
        "Read the MVP scope with the stated skill level and available time. "
        "Score 2 when it is clearly achievable, 1 when it is a reasonable "
        "stretch, and 0 when it is unrealistic."
    )
    distinctiveness_instruction: str = (
        "Assess each planner set as a whole. Score 2 for three meaningfully "
        "different problem angles, 1 for two distinct directions plus one "
        "near-duplicate, and 0 when directions are mostly variations of "
        "the same idea."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ManualCandidateReview:
    candidate_title: str
    goal_alignment: Optional[int] = None
    grounding: Optional[int] = None
    scope_realism: Optional[int] = None
    notes: str = ""

    def validate(self) -> None:
        if not self.candidate_title.strip():
            raise ValueError("Manual review candidate title must be non-empty.")

        for name, score in {
            "goal_alignment": self.goal_alignment,
            "grounding": self.grounding,
            "scope_realism": self.scope_realism,
        }.items():
            if score is not None and score not in SCORE_VALUES:
                raise ValueError(
                    f"{name} must be one of {sorted(SCORE_VALUES)} or None."
                )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class ManualSetReview:
    planner_path: str
    candidate_reviews: List[ManualCandidateReview] = field(
        default_factory=list
    )
    distinctiveness: Optional[int] = None
    notes: str = ""

    def validate(self) -> None:
        if self.planner_path not in {"deterministic", "openai"}:
            raise ValueError(
                "planner_path must be 'deterministic' or 'openai'."
            )

        if (
            self.distinctiveness is not None
            and self.distinctiveness not in SCORE_VALUES
        ):
            raise ValueError(
                "distinctiveness must be 0, 1, 2, or None."
            )

        titles = []

        for review in self.candidate_reviews:
            review.validate()
            titles.append(review.candidate_title.strip().lower())

        if len(titles) != len(set(titles)):
            raise ValueError(
                "Manual set review cannot contain duplicate candidate titles."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "planner_path": self.planner_path,
            "candidate_reviews": [
                review.to_dict()
                for review in self.candidate_reviews
            ],
            "distinctiveness": self.distinctiveness,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ManualReviewRecord:
    rubric_version: str
    query_fingerprint: str
    deterministic_review: ManualSetReview
    openai_review: ManualSetReview
    overall_preference: Optional[str] = None
    overall_preference_reason: str = ""
    response_quality: Optional[str] = None
    response_quality_reason: str = ""
    unique_angle_quality: Optional[str] = None
    unique_angle_quality_reason: str = ""
    reviewer_notes: str = ""

    def validate(self) -> None:
        if not self.rubric_version.strip():
            raise ValueError("rubric_version must be non-empty.")

        if not self.query_fingerprint.strip():
            raise ValueError("query_fingerprint must be non-empty.")

        self.deterministic_review.validate()
        self.openai_review.validate()

        if (
            self.overall_preference is not None
            and self.overall_preference not in PREFERENCE_OPTIONS
        ):
            raise ValueError(
                "overall_preference must be one of "
                f"{sorted(PREFERENCE_OPTIONS)} or None."
            )

        if (
            self.response_quality is not None
            and self.response_quality not in RESPONSE_QUALITY_OPTIONS
        ):
            raise ValueError(
                "response_quality must be one of "
                f"{sorted(RESPONSE_QUALITY_OPTIONS)} or None."
            )

        if (
            self.response_quality is not None
            and not self.response_quality_reason.strip()
        ):
            raise ValueError(
                "response_quality_reason is required when "
                "response_quality is set."
            )

        if (
            self.unique_angle_quality is not None
            and self.unique_angle_quality
            not in UNIQUE_ANGLE_QUALITY_OPTIONS
        ):
            raise ValueError(
                "unique_angle_quality must be one of "
                f"{sorted(UNIQUE_ANGLE_QUALITY_OPTIONS)} or None."
            )

        if (
            self.unique_angle_quality is not None
            and not self.unique_angle_quality_reason.strip()
        ):
            raise ValueError(
                "unique_angle_quality_reason is required when "
                "unique_angle_quality is set."
            )

        if (
            self.overall_preference is not None
            and not self.overall_preference_reason.strip()
        ):
            raise ValueError(
                "overall_preference_reason is required when "
                "overall_preference is set."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return {
            "rubric_version": self.rubric_version,
            "query_fingerprint": self.query_fingerprint,
            "deterministic_review": self.deterministic_review.to_dict(),
            "openai_review": self.openai_review.to_dict(),
            "overall_preference": self.overall_preference,
            "overall_preference_reason": self.overall_preference_reason,
            "response_quality": self.response_quality,
            "response_quality_reason": self.response_quality_reason,
            "unique_angle_quality": self.unique_angle_quality,
            "unique_angle_quality_reason": (
                self.unique_angle_quality_reason
            ),
            "reviewer_notes": self.reviewer_notes,
        }


def build_manual_review_template(
    comparison: Mapping[str, Any],
    rubric: Optional[ManualReviewRubric] = None,
) -> ManualReviewRecord:
    """
    Create an unscored review record from a comparison artifact payload.
    The caller fills scores offline after reviewing raw candidates and evidence.
    """
    rubric = rubric or ManualReviewRubric()

    deterministic_reviews = [
        ManualCandidateReview(
            candidate_title=str(candidate.get("title", "")).strip()
        )
        for candidate in comparison.get(
            "deterministic_candidates",
            [],
        )
        if str(candidate.get("title", "")).strip()
    ]

    openai_reviews = [
        ManualCandidateReview(
            candidate_title=str(candidate.get("title", "")).strip()
        )
        for candidate in comparison.get(
            "openai_candidates",
            [],
        )
        if str(candidate.get("title", "")).strip()
    ]

    return ManualReviewRecord(
        rubric_version=rubric.version,
        query_fingerprint=str(
            comparison.get("query_fingerprint", "")
        ).strip(),
        deterministic_review=ManualSetReview(
            planner_path="deterministic",
            candidate_reviews=deterministic_reviews,
        ),
        openai_review=ManualSetReview(
            planner_path="openai",
            candidate_reviews=openai_reviews,
        ),
    )
