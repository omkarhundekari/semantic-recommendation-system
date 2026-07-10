from __future__ import annotations

from typing import Any


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
