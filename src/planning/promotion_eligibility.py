from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from planning.candidate_feasibility_prescreen import (
    CandidateFeasibilityPrescreen,
)

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.grounding_adequacy import (
    GroundingAdequacy,
    GroundingAdequacyTrace,
)
from planning.semantic_candidate_diversity import (
    CandidateDiversityTrace,
)
from planning.shadow_quality_warnings import (
    ShadowQualityWarningAssessment,
)


@dataclass(frozen=True)
class PromotionEligibilityAssessment:
    candidate_title: str
    status: str
    eligible_for_product_promotion: bool
    blocking_reasons: List[str] = field(default_factory=list)
    review_reasons: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _candidate_warning_codes(
    candidate_title: str,
    quality_warnings: ShadowQualityWarningAssessment,
) -> List[str]:
    codes = []

    for warning in quality_warnings.warnings:
        details = warning.details
        candidates = details.get("candidates", [])
        pairs = details.get("pairs", [])

        applies_to_candidate = any(
            item.get("candidate_title") == candidate_title
            for item in candidates
            if isinstance(item, dict)
        )

        applies_to_candidate = applies_to_candidate or any(
            candidate_title
            in {
                item.get("candidate_a_title"),
                item.get("candidate_b_title"),
            }
            for item in pairs
            if isinstance(item, dict)
        )

        if warning.code == "missing_direct_research_evidence":
            applies_to_candidate = True

        if applies_to_candidate:
            codes.append(warning.code)

    return codes


def _has_flagged_duplicate_pair(
    candidate_title: str,
    diversity: Optional[CandidateDiversityTrace],
) -> bool:
    if diversity is None:
        return False

    return any(
        pair.flagged
        and candidate_title
        in {
            pair.candidate_a_title,
            pair.candidate_b_title,
        }
        for pair in diversity.pairwise_similarity
    )


def assess_promotion_eligibility(
    candidate: CandidateDirection,
    validation: CandidateValidationResult,
    grounding: GroundingAdequacyTrace,
    quality_warnings: ShadowQualityWarningAssessment,
    semantic_candidate_diversity: Optional[
        CandidateDiversityTrace
    ] = None,
    feasibility_prescreen: Optional[
        CandidateFeasibilityPrescreen
    ] = None,
) -> PromotionEligibilityAssessment:
    """
    Assess whether a shadow candidate is structurally safe for a future
    production bridge.

    This does not rerank, repair, or mutate candidates. Numeric relevance and
    grounding concerns remain review signals until more calibration data exists.
    """
    blocking_reasons = []
    review_reasons = []

    if not validation.is_valid:
        blocking_reasons.append(
            "Candidate failed planner validation."
        )

    if grounding.adequacy_class == GroundingAdequacy.INVALID_CITATIONS:
        blocking_reasons.append(
            "Candidate includes evidence IDs outside the curated brief."
        )
    elif (
        grounding.adequacy_class
        != GroundingAdequacy.CITED_WITH_DIRECT_SCOPE
    ):
        blocking_reasons.append(
            "Candidate does not cite directly retained evidence."
        )

    if _has_flagged_duplicate_pair(
        candidate.title,
        semantic_candidate_diversity,
    ):
        blocking_reasons.append(
            "Candidate is part of a semantically duplicate direction pair."
        )

    if feasibility_prescreen is not None:
        if feasibility_prescreen.status == "blocked_by_constraints":
            blocking_reasons.extend(
                feasibility_prescreen.blocking_reasons
            )
        elif feasibility_prescreen.status == "needs_review":
            review_reasons.extend(
                feasibility_prescreen.review_reasons
            )

    warning_codes = _candidate_warning_codes(
        candidate.title,
        quality_warnings,
    )

    review_messages = {
        "missing_direct_research_evidence": (
            "The evidence brief has no research-paper evidence."
        ),
        "low_goal_alignment": (
            "Candidate has low semantic alignment with the requested goal."
        ),
        "weak_grounding_alignment": (
            "Candidate-to-source semantic grounding is weak."
        ),
        "near_duplicate_candidates": (
            "Candidate is semantically close to another direction."
        ),
    }

    for code in warning_codes:
        message = review_messages.get(code)

        if message and message not in review_reasons:
            review_reasons.append(message)

    if blocking_reasons:
        status = "ineligible"
    elif review_reasons:
        status = "needs_review"
    else:
        status = "eligible"

    return PromotionEligibilityAssessment(
        candidate_title=candidate.title,
        status=status,
        eligible_for_product_promotion=(status == "eligible"),
        blocking_reasons=blocking_reasons,
        review_reasons=review_reasons,
        signals={
            "validation_is_valid": validation.is_valid,
            "grounding_adequacy_class": (
                grounding.adequacy_class.value
            ),
            "candidate_warning_codes": warning_codes,
            "has_flagged_duplicate_pair": _has_flagged_duplicate_pair(
                candidate.title,
                semantic_candidate_diversity,
            ),
            "feasibility_prescreen": (
                feasibility_prescreen.to_dict()
                if feasibility_prescreen is not None
                else None
            ),
        },
    )
