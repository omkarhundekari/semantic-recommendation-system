from __future__ import annotations

from typing import Any, Dict, List

from planning.evidence_brief import build_evidence_brief
from planning.live_evidence_cards import build_live_evidence_cards_from_brief
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.llm_routing_policy import (
    DEEP_MODE,
    SessionBudgetState,
    decide_llm_routing,
)
from planning.llm_synthesis_fallback import (
    build_deterministic_synthesis_fallback,
)
from planning.llm_synthesis_output_validator import (
    validate_synthesis_parsed_response_against_cards,
)
from planning.token_estimation import estimate_tokens_for_prompt


def build_synthesis_summary(
    *,
    routing_decision: Any,
    token_estimate: Any,
    evidence_cards: list[Any],
    preview_validation: Any,
) -> dict[str, Any]:
    grounded_direction_count = sum(
        1
        for trace in preview_validation.direction_grounding_traces
        if trace.get("is_grounded")
    )

    if preview_validation.is_valid:
        status = "preview_valid"
    else:
        status = "preview_invalid"

    return {
        "status": status,
        "source": "deterministic_fallback_preview",
        "can_run_llm": routing_decision.should_route,
        "routing_reason": routing_decision.reason,
        "card_count": len(evidence_cards),
        "validated": preview_validation.is_valid,
        "grounded_direction_count": grounded_direction_count,
        "invented_source_count": len(preview_validation.invented_source_ids),
        "estimated_tokens": token_estimate.estimated_tokens,
    }


def build_project_intelligence_synthesis_status(
    *,
    query: str,
    constraints: Dict,
    evidence_items: List[Dict],
) -> Dict:
    brief = build_evidence_brief(
        evidence_items=evidence_items,
        user_query=query,
    )
    evidence_cards = build_live_evidence_cards_from_brief(brief)

    prompt = build_llm_synthesis_prompt(
        user_goal=query,
        constraints=constraints,
        evidence_cards=evidence_cards,
    )
    token_estimate = estimate_tokens_for_prompt(prompt)

    routing_decision = decide_llm_routing(
        evidence_cards=evidence_cards,
        session_budget=SessionBudgetState(
            calls_remaining=1,
            tokens_remaining=10000,
        ),
        mode=DEEP_MODE,
        estimated_tokens=token_estimate.estimated_tokens,
    )

    confidence_counts = {
        "strong_count": sum(
            1
            for card in evidence_cards
            if card.evidence_confidence == "Strong"
        ),
        "limited_count": sum(
            1
            for card in evidence_cards
            if card.evidence_confidence == "Limited"
        ),
        "exploratory_count": sum(
            1
            for card in evidence_cards
            if card.evidence_confidence == "Exploratory"
        ),
    }

    deterministic_preview = build_deterministic_synthesis_fallback(
        evidence_cards=evidence_cards,
    )

    deterministic_preview["synthesis_source"] = (
        "deterministic_fallback_preview"
    )

    preview_validation = validate_synthesis_parsed_response_against_cards(
        parsed_response=deterministic_preview,
        evidence_cards=evidence_cards,
        output_path="live_final_synthesis_preview",
    )

    synthesis_summary = build_synthesis_summary(
        routing_decision=routing_decision,
        token_estimate=token_estimate,
        evidence_cards=evidence_cards,
        preview_validation=preview_validation,
    )

    return {
        "available": False,
        "reason": (
            "live_synthesis_execution_not_enabled_for_project_intelligence"
        ),
        "safe_inspection_endpoint": "/v1/synthesis-demo",
        "current_planning_source": "deterministic_product_pipeline",
        "synthesis_summary": synthesis_summary,
        "live_evidence_cards": {
            "card_count": len(evidence_cards),
            **confidence_counts,
            "query_aligned_card_count": (
                routing_decision.query_aligned_card_count
            ),
            "weak_card_count": routing_decision.weak_card_count,
            "suspicious_card_count": (
                routing_decision.suspicious_card_count
            ),
        },
        "routing_preview": routing_decision.to_dict(),
        "token_estimate": token_estimate.to_dict(),
        "live_final_synthesis_preview": {
            "source": "deterministic_fallback_preview",
            "fallback_used": True,
            "parsed_response": deterministic_preview,
        },
        "live_final_synthesis_preview_validation": (
            preview_validation.to_dict()
        ),
        "safety_pipeline": {
            "raw_output_validation": True,
            "deterministic_fallback": True,
            "final_synthesis_validation": True,
        },
    }
