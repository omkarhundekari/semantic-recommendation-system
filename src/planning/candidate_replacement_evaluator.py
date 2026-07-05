from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.grounding_adequacy import (
    GroundingAdequacy,
    assess_grounding_adequacy,
)
from planning.planner_models import EvidenceBrief
from planning.promotion_eligibility import (
    PromotionEligibilityAssessment,
    assess_promotion_eligibility,
)
from planning.semantic_candidate_diversity import (
    CandidateDiversityTrace,
    SemanticCandidateDiversityScorer,
)
from planning.shadow_quality_warnings import (
    NEAR_DUPLICATE_WARNING_THRESHOLD,
    ShadowQualityWarningAssessment,
    assess_shadow_quality_warnings,
)


@dataclass(frozen=True)
class CandidateReplacementEvaluation:
    candidate_title: str
    replacement_status: str
    accepted_as_diverse_replacement: bool
    ready_for_product_promotion: bool
    validation: Dict[str, Any]
    grounding_adequacy: Dict[str, Any]
    semantic_diversity: Dict[str, Any]
    quality_warnings: Dict[str, Any]
    promotion_eligibility: Dict[str, Any]
    reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _has_close_retained_pair(
    candidate_title: str,
    diversity: CandidateDiversityTrace,
) -> bool:
    return any(
        pair.flagged
        and candidate_title
        in {
            pair.candidate_a_title,
            pair.candidate_b_title,
        }
        for pair in diversity.pairwise_similarity
    )


def evaluate_regenerated_candidate(
    candidate: CandidateDirection,
    validation: CandidateValidationResult,
    retained_candidates: Sequence[CandidateDirection],
    brief: EvidenceBrief,
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
) -> CandidateReplacementEvaluation:
    """
    Evaluate one candidate proposed as a replacement for a close semantic pair.

    This function does not call an LLM or mutate planning state. A candidate
    may be accepted as a diverse replacement while still needing review before
    future product promotion because soft evidence-quality warnings remain.
    """
    retained = list(retained_candidates)

    if not retained:
        raise ValueError(
            "At least one retained candidate is required for replacement "
            "evaluation."
        )

    evidence_assessment = evidence_support_scorer.assess_candidate(
        candidate=candidate,
        brief=brief,
    )
    grounding = assess_grounding_adequacy(
        candidate=candidate,
        brief=brief,
        assessment=evidence_assessment,
    )

    diversity = semantic_diversity_scorer.assess_candidates(
        [*retained, candidate],
        similarity_threshold=NEAR_DUPLICATE_WARNING_THRESHOLD,
    )

    quality_warnings: ShadowQualityWarningAssessment = (
        assess_shadow_quality_warnings(
            coverage_warnings=brief.coverage_warnings,
            semantic_goal_relevance=[],
            grounding_adequacy=[grounding.to_dict()],
            semantic_candidate_diversity=diversity.to_dict(),
        )
    )

    promotion: PromotionEligibilityAssessment = (
        assess_promotion_eligibility(
            candidate=candidate,
            validation=validation,
            grounding=grounding,
            quality_warnings=quality_warnings,
            semantic_candidate_diversity=diversity,
        )
    )

    reasons = []

    if not validation.is_valid:
        reasons.append("Replacement candidate failed validation.")

    if grounding.adequacy_class != GroundingAdequacy.CITED_WITH_DIRECT_SCOPE:
        reasons.append(
            "Replacement candidate does not cite directly retained evidence."
        )

    if _has_close_retained_pair(candidate.title, diversity):
        reasons.append(
            "Replacement candidate remains semantically close to a retained direction."
        )

    accepted_as_diverse_replacement = not reasons

    if not accepted_as_diverse_replacement:
        replacement_status = "rejected"
    elif promotion.eligible_for_product_promotion:
        replacement_status = "accepted"
    else:
        replacement_status = "needs_review"

    return CandidateReplacementEvaluation(
        candidate_title=candidate.title,
        replacement_status=replacement_status,
        accepted_as_diverse_replacement=accepted_as_diverse_replacement,
        ready_for_product_promotion=(
            promotion.eligible_for_product_promotion
        ),
        validation=validation.to_dict(),
        grounding_adequacy=grounding.to_dict(),
        semantic_diversity=diversity.to_dict(),
        quality_warnings=quality_warnings.to_dict(),
        promotion_eligibility=promotion.to_dict(),
        reasons=reasons,
    )
