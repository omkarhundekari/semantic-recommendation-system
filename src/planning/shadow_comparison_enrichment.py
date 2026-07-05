from typing import Any, Dict, List, Mapping, Optional, Sequence

from planning.candidate_models import CandidateDirection
from planning.candidate_provenance import CandidateProvenance
from planning.candidate_to_product_adapter import (
    adapt_candidate_to_product_idea,
)
from planning.planner_models import EvidenceBrief
from planning.product_enrichment import enrich_product_ideas
from planning.shadow_vs_deterministic_comparison import (
    build_shadow_vs_deterministic_comparison,
)


def _candidate_from_payload(
    payload: Mapping[str, Any],
) -> CandidateDirection:
    return CandidateDirection(
        **{
            key: value
            for key, value in payload.items()
            if key != "ranking"
        }
    )


def _by_title(
    items: Sequence[Mapping[str, Any]],
    title_field: str,
) -> Dict[str, Mapping[str, Any]]:
    return {
        str(item.get(title_field, "")).strip(): item
        for item in items
        if str(item.get(title_field, "")).strip()
    }


def build_shadow_comparison_enrichment(
    user_goal: str,
    constraints: Dict[str, Any],
    detected_domain: str,
    brief: EvidenceBrief,
    legacy_ideas: Sequence[Mapping[str, Any]],
    selected_candidates: Sequence[Mapping[str, Any]],
    grounding_adequacy: Sequence[Mapping[str, Any]],
    promotion_eligibility: Mapping[str, Any],
    generation_metadata: Mapping[str, Any],
    comparison_encoder: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Build complete, reproducible enrichment inputs for deterministic-vs-shadow
    evaluation. This never generates candidates or calls an LLM.
    """
    deterministic_raw_ideas = [
        dict(idea)
        for idea in legacy_ideas
    ]
    deterministic_enrichment = enrich_product_ideas(
        ideas=deterministic_raw_ideas,
        constraints=constraints,
    )

    selected = [
        _candidate_from_payload(candidate)
        for candidate in selected_candidates
    ]

    grounding_by_title = _by_title(
        grounding_adequacy,
        "candidate_title",
    )
    promotion_by_title = _by_title(
        promotion_eligibility.get("candidate_assessments", []),
        "candidate_title",
    )

    shadow_ideas: List[Dict[str, Any]] = []

    for candidate in selected:
        grounding = grounding_by_title.get(candidate.title, {})
        promotion = promotion_by_title.get(candidate.title, {})

        provenance = CandidateProvenance(
            planning_source="openai",
            prompt_version=generation_metadata.get("prompt_version"),
            generation_attempt=1,
            grounding_adequacy=grounding.get("adequacy_class"),
            diversity_check_passed=(
                promotion.get("signals", {})
                .get("has_flagged_duplicate_pair") is False
                if promotion
                else None
            ),
            promotion_eligible=promotion.get(
                "eligible_for_product_promotion"
            ),
        )

        shadow_ideas.append(
            adapt_candidate_to_product_idea(
                candidate=candidate,
                brief=brief,
                detected_domain=detected_domain or "general",
                target_roles=list(
                    constraints.get("target_roles", [])
                ),
                planner_provenance=provenance,
            )
        )

    shadow_enrichment = enrich_product_ideas(
        ideas=shadow_ideas,
        constraints=constraints,
    )

    comparison = build_shadow_vs_deterministic_comparison(
        user_goal=user_goal,
        constraints=constraints,
        deterministic_candidates=deterministic_raw_ideas,
        openai_candidates=selected,
        deterministic_enriched_ideas=deterministic_enrichment.ideas,
        openai_enriched_ideas=shadow_enrichment.ideas,
        openai_grounding_adequacy=grounding_adequacy,
        encoder=comparison_encoder,
    )

    return {
        "legacy_raw_ideas": deterministic_raw_ideas,
        "legacy_enrichment": deterministic_enrichment.to_dict(),
        "shadow_raw_candidates": [
            candidate.to_dict()
            for candidate in selected
        ],
        "shadow_enrichment": shadow_enrichment.to_dict(),
        "comparison": comparison.to_dict(),
    }
