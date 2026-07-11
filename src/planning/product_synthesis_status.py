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
from planning.presentation_layer import build_presentation_project_directions
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


def build_validated_project_directions(
    *,
    parsed_response: dict[str, Any],
    preview_validation: Any,
) -> list[dict[str, Any]]:
    if not preview_validation.is_valid:
        return []

    project_directions = parsed_response.get("project_directions", [])
    if not isinstance(project_directions, list):
        return []

    validated_directions = []
    for direction in project_directions:
        if not isinstance(direction, dict):
            continue

        validated_directions.append(
            {
                "scope_level": direction.get("scope_level"),
                "build_type": direction.get("build_type"),
                "estimated_time": direction.get("estimated_time"),
                "title": direction.get("title"),
                "evidence_confidence": direction.get(
                    "evidence_confidence"
                ),
                "source_ids": direction.get("source_ids", []),
                "grounding_warnings": direction.get(
                    "grounding_warnings",
                    [],
                ),
            }
        )

    return validated_directions


def build_project_intelligence_synthesis_status(
    *,
    query: str,
    constraints: Dict,
    evidence_items: List[Dict],
    project_directions: List[object] | None = None,
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

    validated_project_directions = build_validated_project_directions(
        parsed_response=deterministic_preview,
        preview_validation=preview_validation,
    )

    presentation_project_directions = build_presentation_project_directions(
        parsed_response=deterministic_preview,
        evidence_cards=evidence_cards,
        preview_validation=preview_validation,
    )

    frontend_project_directions = build_frontend_project_directions(
        project_directions=project_directions or [],
        presentation_project_directions=presentation_project_directions,
    )

    return {
        "available": False,
        "reason": (
            "live_synthesis_execution_not_enabled_for_project_intelligence"
        ),
        "safe_inspection_endpoint": "/v1/synthesis-demo",
        "current_planning_source": "deterministic_product_pipeline",
        "synthesis_summary": synthesis_summary,
        "validated_project_directions": validated_project_directions,
        "presentation_project_directions": presentation_project_directions,
        "frontend_project_directions": frontend_project_directions,
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


def build_frontend_project_directions(
    *,
    project_directions: List[object],
    presentation_project_directions: List[Dict],
) -> List[Dict]:
    frontend_directions = []

    for index, project_direction in enumerate(project_directions):
        presentation = (
            presentation_project_directions[index]
            if index < len(presentation_project_directions)
            else {}
        )

        frontend_directions.append(
            {
                "id": _read_field(project_direction, "id", f"direction-{index + 1}"),
                "title": _read_field(
                    project_direction,
                    "title",
                    f"Project Direction {index + 1}",
                ),
                "tier": _read_field(
                    project_direction,
                    "portfolio_tier",
                    "Portfolio Build",
                ),
                "level": _level_from_difficulty(
                    _read_field(project_direction, "difficulty", "Medium")
                ),
                "estimated_time": _read_field(
                    project_direction,
                    "estimated_effort",
                    "Flexible",
                ),
                "summary": _read_field(project_direction, "summary", ""),
                "evidence_badge": _read_field(
                    presentation,
                    "evidence_badge",
                    "Evidence-informed",
                ),
                "confidence_explanation": _read_field(
                    presentation,
                    "confidence_explanation",
                    "This direction is supported by the available evidence.",
                ),
                "evidence_summary": _read_field(
                    presentation,
                    "evidence_summary",
                    "Evidence-informed",
                ),
                "skills_shown": _read_field(
                    presentation,
                    "skills_shown",
                    [],
                ),
                "why_it_matters": _read_field(
                    presentation,
                    "why_it_matters",
                    _read_field(project_direction, "why_it_fits", ""),
                ),
                "interview_talking_point": _read_field(
                    presentation,
                    "interview_talking_point",
                    "Explain how this project turns evidence into a practical build.",
                ),
                "open_questions": _read_field(
                    presentation,
                    "open_questions",
                    [],
                ),
                "roadmap": _serialize_list(
                    _read_field(project_direction, "roadmap", []),
                ),
            }
        )

    return frontend_directions


def _read_field(value: object, field_name: str, default: object) -> object:
    if isinstance(value, dict):
        return value.get(field_name, default)

    return getattr(value, field_name, default)


def _serialize_list(values: object) -> List[Dict]:
    if not isinstance(values, list):
        return []

    serialized = []
    for value in values:
        if hasattr(value, "model_dump"):
            serialized.append(value.model_dump())
        elif isinstance(value, dict):
            serialized.append(value)

    return serialized


def _level_from_difficulty(difficulty: object) -> str:
    if difficulty == "Easy":
        return "Beginner"

    if difficulty == "Hard":
        return "Advanced"

    return "Intermediate"
