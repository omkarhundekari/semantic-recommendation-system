from __future__ import annotations

from typing import Any

from planning.evidence_cards import (
    ADJACENT_SUPPORT_SCOPE,
    DIRECT_SUPPORT_SCOPE,
    EvidenceCard,
)


def build_live_evidence_cards_from_brief(
    brief: Any,
) -> list[EvidenceCard]:
    sources = list(getattr(brief, "sources", []))

    has_research_paper = any(
        getattr(source, "source_type", "") == "research_paper"
        for source in sources
    )

    artifact_confidence = _infer_live_evidence_confidence(
        sources=sources,
        has_research_paper=has_research_paper,
    )

    cards = []

    for source in sources:
        support_scope = (
            getattr(source, "support_scope", "") or DIRECT_SUPPORT_SCOPE
        )
        source_type = getattr(source, "source_type", "") or "unknown"

        grounding_warning = _select_live_grounding_warning(
            support_scope=support_scope,
            source_type=source_type,
            has_research_paper=has_research_paper,
        )

        cards.append(
            EvidenceCard(
                source_id=str(getattr(source, "source_id", "")),
                source_type=source_type,
                title=str(getattr(source, "title", "")),
                support_scope=support_scope,
                evidence_confidence=_infer_live_card_confidence(
                    artifact_confidence=artifact_confidence,
                    support_scope=support_scope,
                    grounding_warning=grounding_warning,
                ),
                key_excerpt=str(getattr(source, "excerpt", "")),
                specific_method_or_technique=_first_recurring_or_signal(
                    brief,
                    source,
                ),
                specific_dataset_or_benchmark=None,
                specific_implementation_signal=_implementation_signal(source),
                grounding_warning=grounding_warning,
                relevance_signal=(
                    "plausible"
                    if support_scope == DIRECT_SUPPORT_SCOPE
                    else "weak"
                ),
                relevance_statuses=(
                    ("lexically_supported",)
                    if support_scope == DIRECT_SUPPORT_SCOPE
                    else ("adjacent_context_only",)
                ),
                linked_candidate_titles=(),
                user_facing_explanation=_build_live_explanation(
                    source=source,
                    support_scope=support_scope,
                    grounding_warning=grounding_warning,
                ),
            )
        )

    return cards


def build_live_evidence_card_payload_from_brief(
    brief: Any,
) -> dict[str, Any]:
    cards = build_live_evidence_cards_from_brief(brief)

    return {
        "query": getattr(brief, "query", ""),
        "card_count": len(cards),
        "evidence_cards": [card.to_dict() for card in cards],
    }


def _infer_live_evidence_confidence(
    *,
    sources: list[Any],
    has_research_paper: bool,
) -> str:
    direct_count = sum(
        1
        for source in sources
        if getattr(source, "support_scope", "") == DIRECT_SUPPORT_SCOPE
    )
    adjacent_count = sum(
        1
        for source in sources
        if getattr(source, "support_scope", "") == ADJACENT_SUPPORT_SCOPE
    )

    if direct_count == 0:
        return "Exploratory"
    if not has_research_paper:
        return "Limited"
    if adjacent_count > 0:
        return "Limited"
    return "Strong"


def _infer_live_card_confidence(
    *,
    artifact_confidence: str,
    support_scope: str,
    grounding_warning: str | None,
) -> str:
    if support_scope != DIRECT_SUPPORT_SCOPE:
        return "Exploratory"
    if grounding_warning:
        return "Limited"
    return artifact_confidence


def _select_live_grounding_warning(
    *,
    support_scope: str,
    source_type: str,
    has_research_paper: bool,
) -> str | None:
    if support_scope != DIRECT_SUPPORT_SCOPE:
        return "adjacent_evidence"
    if not has_research_paper and source_type != "research_paper":
        return "implementation_only_evidence"
    return None


def _first_recurring_or_signal(
    brief: Any,
    source: Any,
) -> str | None:
    recurring = list(getattr(brief, "recurring_concepts", []) or [])

    if recurring:
        return str(recurring[0])

    excerpt = str(getattr(source, "excerpt", "")).lower()

    for term in [
        "retrieval",
        "evaluation",
        "lineage",
        "monitoring",
        "dashboard",
        "ranking",
        "automation",
    ]:
        if term in excerpt:
            return term

    return None


def _implementation_signal(source: Any) -> str | None:
    text = " ".join(
        [
            str(getattr(source, "title", "")),
            str(getattr(source, "excerpt", "")),
        ]
    ).lower()

    for term in [
        "dashboard",
        "api",
        "repository",
        "python",
        "fastapi",
        "react",
        "postgres",
        "workflow",
    ]:
        if term in text:
            return term

    return None


def _build_live_explanation(
    *,
    source: Any,
    support_scope: str,
    grounding_warning: str | None,
) -> str:
    title = str(getattr(source, "title", "This source")).strip()

    if support_scope == DIRECT_SUPPORT_SCOPE and not grounding_warning:
        return (
            f"{title} is direct live evidence for the user's project "
            "direction."
        )

    if grounding_warning == "implementation_only_evidence":
        return (
            f"{title} is implementation evidence. It can support build "
            "planning, but it is not research-paper evidence."
        )

    return (
        f"{title} is adjacent live evidence. It can support planning context, "
        "but should not be treated as strong direct support."
    )
