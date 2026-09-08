from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from planning.candidate_feasibility_prescreen import (
    prescreen_candidate_feasibility,
)
from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_validator import validate_candidate
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.grounding_adequacy import assess_grounding_adequacy
from planning.planner_models import EvidenceBrief
from planning.promotion_eligibility import assess_promotion_eligibility
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
class CandidateSetAssessment:
    status: str
    semantic_candidate_diversity: Optional[Dict[str, Any]]
    grounding_adequacy: List[Dict[str, Any]]
    quality_warnings: Dict[str, Any]
    promotion_eligibility: List[Dict[str, Any]]
    signals: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assess_candidate_set(
    candidates: List[CandidateDirection],
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    detected_domain: Optional[str],
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: Optional[
        SemanticCandidateDiversityScorer
    ],
    semantic_candidate_diversity: Optional[
        CandidateDiversityTrace
    ] = None,
    quality_warnings: Optional[
        ShadowQualityWarningAssessment
    ] = None,
) -> CandidateSetAssessment:
    if semantic_candidate_diversity is not None:
        diversity = semantic_candidate_diversity
    elif semantic_diversity_scorer is not None:
        diversity = semantic_diversity_scorer.assess_candidates(
            candidates,
            similarity_threshold=NEAR_DUPLICATE_WARNING_THRESHOLD,
        )
    else:
        diversity = None

    grounding = []
    for candidate in candidates:
        support = evidence_support_scorer.assess_candidate(
            candidate=candidate,
            brief=brief,
        )
        grounding.append(
            assess_grounding_adequacy(
                candidate=candidate,
                brief=brief,
                assessment=support,
            )
        )

    quality_warnings = (
        quality_warnings
        if quality_warnings is not None
        else assess_shadow_quality_warnings(
            coverage_warnings=brief.coverage_warnings,
            semantic_goal_relevance=[],
            grounding_adequacy=[
                item.to_dict()
                for item in grounding
            ],
            semantic_candidate_diversity=(
                diversity.to_dict()
                if diversity is not None
                else None
            ),
        )
    )

    feasibility = (
        [
            prescreen_candidate_feasibility(
                candidate=candidate,
                brief=brief,
                request=request,
                detected_domain=detected_domain,
            )
            for candidate in candidates
        ]
        if detected_domain
        else [None] * len(candidates)
    )

    promotion = [
        assess_promotion_eligibility(
            candidate=candidate,
            validation=validate_candidate(candidate, brief),
            grounding=grounding_trace,
            quality_warnings=quality_warnings,
            semantic_candidate_diversity=diversity,
            feasibility_prescreen=feasibility_prescreen,
        ).to_dict()
        for candidate, grounding_trace, feasibility_prescreen in zip(
            candidates,
            grounding,
            feasibility,
        )
    ]

    eligible_count = sum(
        item["eligible_for_product_promotion"]
        for item in promotion
    )

    hard_blockers = [
        code
        for item in promotion
        for code in item["blocking_reason_codes"]
        if code != "semantic_duplicate"
    ]
    needs_review = any(
        item["status"] == "needs_review"
        for item in promotion
    )

    if not candidates or hard_blockers:
        status = "blocked"
    elif diversity is None:
        status = "needs_review"
    elif not diversity.passed:
        status = "needs_repair"
    elif needs_review:
        status = "needs_review"
    elif eligible_count == len(candidates):
        status = "ready"
    else:
        status = "blocked"

    return CandidateSetAssessment(
        status=status,
        semantic_candidate_diversity=(
            diversity.to_dict()
            if diversity is not None
            else None
        ),
        grounding_adequacy=[
            item.to_dict()
            for item in grounding
        ],
        quality_warnings=quality_warnings.to_dict(),
        promotion_eligibility=promotion,
        signals={
            "candidate_count": len(candidates),
            "semantic_diversity_assessed": diversity is not None,
            "semantic_diversity_passed": (
                diversity.passed
                if diversity is not None
                else None
            ),
            "eligible_candidate_count": eligible_count,
            "feasibility_assessed": bool(detected_domain),
        },
    )
