from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from planning.candidate_models import CandidateDirection
from planning.candidate_ranker import (
    RankedCandidate,
    rank_candidates,
    select_diverse_candidates,
)
from planning.candidate_validator import validate_candidate
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.grounding_adequacy import assess_grounding_adequacy
from planning.promotion_eligibility import (
    assess_promotion_eligibility,
)
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.shadow_quality_warnings import (
    NEAR_DUPLICATE_WARNING_THRESHOLD,
    assess_shadow_quality_warnings,
)


@dataclass(frozen=True)
class RepairedShadowSetEvaluation:
    status: str
    replaced_candidate_title: str
    replacement_candidate_title: str
    ranked_candidates: List[Dict[str, Any]]
    selected_candidates: List[Dict[str, Any]]
    semantic_candidate_diversity: Dict[str, Any]
    grounding_adequacy: List[Dict[str, Any]]
    quality_warnings: Dict[str, Any]
    promotion_eligibility: List[Dict[str, Any]]
    signals: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ranked_payload(item: RankedCandidate) -> Dict[str, Any]:
    return {
        **item.candidate.to_dict(),
        "ranking": {
            "score": item.score,
            "score_breakdown": dict(item.score_breakdown),
            "reasons": list(item.reasons),
        },
    }


def evaluate_repaired_shadow_set(
    source: RegenerationSourceArtifact,
    replacement: CandidateDirection,
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
) -> RepairedShadowSetEvaluation:
    """
    Rebuild and assess a complete shadow candidate set after one accepted
    regeneration. This does not call an LLM or modify source artifacts.
    """
    candidates = [
        *source.surviving_candidates,
        replacement,
    ]

    titles = [candidate.title.strip() for candidate in candidates]

    if not all(titles) or len(set(titles)) != len(titles):
        raise ValueError(
            "Repaired candidate set must contain unique non-empty titles."
        )

    ranked = rank_candidates(
        candidates=candidates,
        brief=source.brief,
        request=source.request,
    )
    selected_ranked = select_diverse_candidates(
        ranked_candidates=ranked,
        max_candidates=len(candidates),
    )
    selected = [
        item.candidate
        for item in selected_ranked
    ]

    diversity = semantic_diversity_scorer.assess_candidates(
        selected,
        similarity_threshold=NEAR_DUPLICATE_WARNING_THRESHOLD,
    )

    grounding = []
    for candidate in selected:
        support = evidence_support_scorer.assess_candidate(
            candidate=candidate,
            brief=source.brief,
        )
        grounding.append(
            assess_grounding_adequacy(
                candidate=candidate,
                brief=source.brief,
                assessment=support,
            )
        )

    quality_warnings = assess_shadow_quality_warnings(
        coverage_warnings=source.brief.coverage_warnings,
        semantic_goal_relevance=[],
        grounding_adequacy=[
            item.to_dict()
            for item in grounding
        ],
        semantic_candidate_diversity=diversity.to_dict(),
    )

    promotion = [
        assess_promotion_eligibility(
            candidate=candidate,
            validation=validate_candidate(
                candidate,
                source.brief,
            ),
            grounding=grounding_trace,
            quality_warnings=quality_warnings,
            semantic_candidate_diversity=diversity,
        ).to_dict()
        for candidate, grounding_trace in zip(selected, grounding)
    ]

    selection_preserved = len(selected) == len(candidates)
    all_eligible = bool(promotion) and all(
        item["eligible_for_product_promotion"]
        for item in promotion
    )

    status = (
        "repaired_ready"
        if selection_preserved and diversity.passed and all_eligible
        else "needs_review"
    )

    return RepairedShadowSetEvaluation(
        status=status,
        replaced_candidate_title=source.replaced_candidate.title,
        replacement_candidate_title=replacement.title,
        ranked_candidates=[
            _ranked_payload(item)
            for item in ranked
        ],
        selected_candidates=[
            _ranked_payload(item)
            for item in selected_ranked
        ],
        semantic_candidate_diversity=diversity.to_dict(),
        grounding_adequacy=[
            item.to_dict()
            for item in grounding
        ],
        quality_warnings=quality_warnings.to_dict(),
        promotion_eligibility=promotion,
        signals={
            "input_candidate_count": len(candidates),
            "selected_candidate_count": len(selected),
            "lexical_selection_preserved": selection_preserved,
            "semantic_diversity_passed": diversity.passed,
            "eligible_candidate_count": sum(
                item["eligible_for_product_promotion"]
                for item in promotion
            ),
        },
    )
