from __future__ import annotations

from typing import Any, Sequence

from planning.evidence_cards import EvidenceCard


SCOPED_FALLBACK_DIRECTIONS = (
    ("easy", "quick_build", "1-2 days"),
    ("medium", "resume_mvp", "3-5 days"),
    ("hard", "flagship_extension", "1-2 weeks"),
)


def build_deterministic_synthesis_fallback(
    *,
    evidence_cards: Sequence[EvidenceCard],
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_cards = _select_supporting_cards(evidence_cards)
    confidence = _overall_confidence(selected_cards)
    warnings = _collect_warnings(selected_cards)

    return {
        "project_directions": [
            _build_fallback_direction(
                cards=selected_cards,
                scope_level=scope_level,
                build_type=build_type,
                estimated_time=estimated_time,
                evidence_confidence=confidence,
            )
            for scope_level, build_type, estimated_time
            in SCOPED_FALLBACK_DIRECTIONS
        ],
        "overall_confidence": confidence,
        "assumptions": [
            "This deterministic fallback was generated because LLM synthesis did not pass validation.",
            "Project directions are derived only from available evidence cards.",
        ],
        "warnings": _merge_validation_warnings(
            evidence_warnings=warnings,
            validation=validation,
        ),
        "synthesis_source": "deterministic_fallback",
    }


def should_use_deterministic_fallback(
    validation: dict[str, Any] | None,
) -> bool:
    if not validation:
        return True
    return not bool(validation.get("is_valid"))


def _select_supporting_cards(
    evidence_cards: Sequence[EvidenceCard],
) -> list[EvidenceCard]:
    cards = list(evidence_cards)
    direct_plausible = [
        card
        for card in cards
        if card.support_scope == "direct"
        and card.relevance_signal == "plausible"
    ]

    if direct_plausible:
        return direct_plausible[:3]

    return cards[:3]


def _overall_confidence(cards: Sequence[EvidenceCard]) -> str:
    confidences = {card.evidence_confidence for card in cards}

    if "Strong" in confidences and confidences <= {"Strong"}:
        return "Strong"
    if "Limited" in confidences:
        return "Limited"
    return "Exploratory"


def _collect_warnings(cards: Sequence[EvidenceCard]) -> list[str]:
    warnings = sorted({
        card.grounding_warning
        for card in cards
        if card.grounding_warning
    })
    if not warnings:
        return []
    return warnings


def _merge_validation_warnings(
    *,
    evidence_warnings: Sequence[str],
    validation: dict[str, Any] | None,
) -> list[str]:
    warnings = list(evidence_warnings)

    if validation:
        errors = validation.get("errors", [])
        failure_categories = validation.get("failure_categories", [])

        if failure_categories:
            warnings.append(
                "LLM synthesis failed validation categories: "
                + ", ".join(failure_categories)
            )

        if errors:
            warnings.append(
                "LLM synthesis validation errors: "
                + ", ".join(errors)
            )

    return warnings


def _build_fallback_direction(
    *,
    cards: Sequence[EvidenceCard],
    scope_level: str,
    build_type: str,
    estimated_time: str,
    evidence_confidence: str,
) -> dict[str, Any]:
    source_ids = [card.source_id for card in cards]
    source_titles = [card.title for card in cards]
    methods = [
        signal
        for card in cards
        for signal in [
            card.specific_method_or_technique,
            card.specific_implementation_signal,
        ]
        if signal
    ]

    title = _fallback_title(
        scope_level=scope_level,
        source_titles=source_titles,
    )

    return {
        "scope_level": scope_level,
        "build_type": build_type,
        "estimated_time": estimated_time,
        "title": title,
        "problem_statement": (
            "Build a project direction grounded in the available evidence "
            "cards while preserving uncertainty from the validation layer."
        ),
        "target_user": "students and early-career engineers",
        "why_this_is_grounded": (
            "This fallback cites only source IDs present in the evidence "
            "cards: " + ", ".join(source_ids)
        ),
        "source_ids": source_ids,
        "evidence_confidence": evidence_confidence,
        "grounding_warnings": _collect_warnings(cards),
        "mvp_scope": _mvp_scope(scope_level=scope_level, methods=methods),
        "advanced_extensions": [
            "Add validation reports for every generated recommendation.",
            "Compare deterministic and LLM-generated directions across fixtures.",
            "Expose evidence confidence and grounding warnings in the product UI.",
        ],
        "skills_demonstrated": [
            "evidence-grounded planning",
            "validation-driven LLM safety",
            "deterministic fallback design",
        ],
        "resume_bullet": (
            "Built a validation-safe project synthesis fallback that converts "
            "evidence cards into grounded project directions when LLM output "
            "fails validation."
        ),
        "interview_talking_points": [
            "Explain why invalid LLM output should not be shown directly.",
            "Describe how evidence cards constrain fallback generation.",
            "Show how failure categories preserve observability.",
        ],
    }


def _fallback_title(
    *,
    scope_level: str,
    source_titles: Sequence[str],
) -> str:
    if source_titles:
        anchor = source_titles[0]
    else:
        anchor = "Evidence-Grounded Project"

    labels = {
        "easy": "Quick Evidence Trace",
        "medium": "Evidence-Grounded MVP",
        "hard": "Validation-Safe Project Engine",
    }

    return f"{labels.get(scope_level, 'Evidence-Grounded Direction')}: {anchor}"


def _mvp_scope(
    *,
    scope_level: str,
    methods: Sequence[str],
) -> list[str]:
    unique_methods = []
    for method in methods:
        if method not in unique_methods:
            unique_methods.append(method)

    base_steps = [
        "Load evidence cards from a reviewed artifact.",
        "Select valid source IDs and preserve grounding warnings.",
        "Render project directions with confidence and cited sources.",
    ]

    if scope_level == "easy":
        return base_steps

    if scope_level == "medium":
        return base_steps + [
            "Add validation failure categories to the fallback response.",
            "Write markdown output for human review.",
        ]

    return base_steps + [
        "Add batch evaluation across reviewed fixtures.",
        "Compare fallback output against validated LLM synthesis.",
        "Track grounding coverage and failure taxonomy over time.",
    ]
