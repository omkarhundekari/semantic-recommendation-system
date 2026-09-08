from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from planning.candidate_models import CandidateDirection
from planning.candidate_ranker import (
    RankedCandidate,
    rank_candidates,
    select_diverse_candidates,
)
from planning.candidate_set_gate import assess_candidate_set
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
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

    gate = assess_candidate_set(
        candidates=selected,
        brief=source.brief,
        request=source.request,
        detected_domain=None,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )

    selection_preserved = len(selected) == len(candidates)
    status = (
        "repaired_ready"
        if selection_preserved and gate.status == "ready"
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
        semantic_candidate_diversity=gate.semantic_candidate_diversity,
        grounding_adequacy=gate.grounding_adequacy,
        quality_warnings=gate.quality_warnings,
        promotion_eligibility=gate.promotion_eligibility,
        signals={
            "input_candidate_count": len(candidates),
            "selected_candidate_count": len(selected),
            "lexical_selection_preserved": selection_preserved,
            "semantic_diversity_passed": gate.signals[
                "semantic_diversity_passed"
            ],
            "eligible_candidate_count": gate.signals[
                "eligible_candidate_count"
            ],
        },
    )
