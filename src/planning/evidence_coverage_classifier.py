from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable


STRONG_DIRECT = "strong_direct"
ADEQUATE_DIRECT = "adequate_direct"
ADJACENT_ONLY = "adjacent_only"
EXPLORATORY = "exploratory"
CROSS_DOMAIN = "cross_domain"
OUT_OF_DOMAIN = "out_of_domain"
QUERY_TOO_BROAD = "query_too_broad"

DIRECT_SUPPORT_SCOPE = "direct"

QUERY_STOP_WORDS = {
    "app",
    "application",
    "build",
    "builder",
    "for",
    "idea",
    "ideas",
    "project",
    "system",
    "tool",
}


@dataclass(frozen=True)
class EvidenceCoverageReport:
    coverage_state: str
    label: str
    user_message: str
    can_generate_directions: bool
    should_ask_clarification: bool = False
    should_offer_exploratory_mode: bool = False
    warnings: list[str] = field(default_factory=list)
    direct_count: int = 0
    adjacent_count: int = 0
    weak_count: int = 0
    unique_source_count: int = 0


def classify_evidence_coverage(
    evidence_cards: Iterable[Any],
    *,
    query: str | None = None,
    detected_domain: str | None = None,
    supported_domains: set[str] | None = None,
    domain_inference: dict[str, Any] | None = None,
    query_metadata: dict[str, Any] | None = None,
) -> EvidenceCoverageReport:
    cards = list(evidence_cards or [])
    domain_inference = domain_inference or {}
    query_metadata = query_metadata or {}
    query_anchors = _query_anchors(query or query_metadata.get("corrected_query", ""))

    direct_count = sum(
        1 for card in cards if _is_direct(card, query_anchors=query_anchors)
    )
    adjacent_count = sum(
        1 for card in cards if _is_adjacent(card, query_anchors=query_anchors)
    )
    weak_count = sum(
        1 for card in cards if _is_weak(card, query_anchors=query_anchors)
    )
    unique_source_count = len(
        {
            source_id
            for source_id in (_read(card, "source_id") for card in cards)
            if source_id
        }
    )

    if _query_requires_clarification(domain_inference, query_metadata):
        return EvidenceCoverageReport(
            coverage_state=QUERY_TOO_BROAD,
            label="Clarification needed",
            user_message=(
                "This goal is too broad or ambiguous. Narrow the technical "
                "direction before generating project paths."
            ),
            can_generate_directions=False,
            should_ask_clarification=True,
            warnings=["query_requires_clarification"],
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    if _looks_cross_domain(domain_inference):
        return EvidenceCoverageReport(
            coverage_state=CROSS_DOMAIN,
            label="Cross-domain goal",
            user_message=(
                "This goal appears to span multiple technical domains. Solvyn "
                "should separate the subproblems before recommending directions."
            ),
            can_generate_directions=True,
            should_ask_clarification=False,
            warnings=["cross_domain_query"],
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    if _is_out_of_domain(
        detected_domain=detected_domain,
        supported_domains=supported_domains,
        direct_count=direct_count,
        adjacent_count=adjacent_count,
    ):
        return EvidenceCoverageReport(
            coverage_state=OUT_OF_DOMAIN,
            label="Outside current corpus",
            user_message=(
                "This topic is outside the strongest current corpus coverage. "
                "Offer an adjacent supported path or an explicitly exploratory path."
            ),
            can_generate_directions=False,
            should_offer_exploratory_mode=True,
            warnings=["out_of_domain"],
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    if direct_count >= 3 and weak_count == 0 and unique_source_count >= 3:
        return EvidenceCoverageReport(
            coverage_state=STRONG_DIRECT,
            label="Strong direct evidence",
            user_message=(
                "This goal has strong direct evidence. Generate full project "
                "directions with high confidence."
            ),
            can_generate_directions=True,
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    if direct_count >= 1:
        return EvidenceCoverageReport(
            coverage_state=ADEQUATE_DIRECT,
            label="Limited direct evidence",
            user_message=(
                "This goal has direct evidence, but coverage is limited. Generate "
                "directions with clear caveats and open questions."
            ),
            can_generate_directions=True,
            warnings=["limited_direct_evidence"],
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    if adjacent_count > 0:
        return EvidenceCoverageReport(
            coverage_state=ADJACENT_ONLY,
            label="Adjacent evidence only",
            user_message=(
                "This goal has related evidence, but not direct support. Generate "
                "evidence-adjacent directions with explicit caveats."
            ),
            can_generate_directions=True,
            should_offer_exploratory_mode=True,
            warnings=["adjacent_evidence_only"],
            direct_count=direct_count,
            adjacent_count=adjacent_count,
            weak_count=weak_count,
            unique_source_count=unique_source_count,
        )

    return EvidenceCoverageReport(
        coverage_state=EXPLORATORY,
        label="Exploratory",
        user_message=(
            "Solvyn found little or no meaningful evidence for this exact goal. "
            "Use exploratory mode or ask the user to narrow the topic."
        ),
        can_generate_directions=False,
        should_offer_exploratory_mode=True,
        warnings=["low_evidence"],
        direct_count=direct_count,
        adjacent_count=adjacent_count,
        weak_count=weak_count,
        unique_source_count=unique_source_count,
    )


def _read(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)

    return getattr(value, key, default)


def _is_direct(card: Any, *, query_anchors: set[str]) -> bool:
    return (
        _read(card, "support_scope") == DIRECT_SUPPORT_SCOPE
        and _has_query_anchor_overlap(card, query_anchors=query_anchors)
        and not _is_weak(card, query_anchors=query_anchors)
    )


def _is_adjacent(card: Any, *, query_anchors: set[str]) -> bool:
    support_scope = str(_read(card, "support_scope", "") or "")
    if support_scope and support_scope != DIRECT_SUPPORT_SCOPE:
        return True

    return (
        support_scope == DIRECT_SUPPORT_SCOPE
        and not _has_query_anchor_overlap(card, query_anchors=query_anchors)
    )


def _is_weak(card: Any, *, query_anchors: set[str]) -> bool:
    relevance_signal = str(_read(card, "relevance_signal", "") or "").lower()
    evidence_confidence = str(
        _read(card, "evidence_confidence", "") or ""
    ).lower()
    relevance_statuses = _read(card, "relevance_statuses", []) or []

    return (
        relevance_signal == "weak"
        or evidence_confidence == "exploratory"
        or "weak" in {str(status).lower() for status in relevance_statuses}
    )


def _query_anchors(query: str) -> set[str]:
    anchors = {
        token
        for token in re.findall(r"[a-z][a-z0-9]{1,}", query.lower())
        if token not in QUERY_STOP_WORDS
    }

    expanded = set(anchors)

    if "rag" in anchors:
        expanded.update({"retrieval augmented generation"})
    if "vr" in anchors:
        expanded.update({"virtual reality"})
    if "ar" in anchors:
        expanded.update({"augmented reality"})
    if "react" in anchors:
        expanded.update({"frontend", "component", "ui"})
    if "frontend" in anchors:
        expanded.update({"react", "component", "ui"})

    return expanded


def _card_text(card: Any) -> str:
    return " ".join(
        str(_read(card, key, "") or "")
        for key in [
            "title",
            "key_excerpt",
            "specific_method_or_technique",
            "specific_implementation_signal",
            "user_facing_explanation",
        ]
    ).lower()


def _has_query_anchor_overlap(card: Any, *, query_anchors: set[str]) -> bool:
    if not query_anchors:
        return True

    card_text = _card_text(card)
    return any(
        _anchor_matches_text(anchor, card_text)
        for anchor in query_anchors
    )


def _anchor_matches_text(anchor: str, text: str) -> bool:
    anchor = anchor.strip().lower()

    if not anchor:
        return False

    if " " in anchor:
        return anchor in text

    return bool(
        re.search(rf"(?<![a-z0-9]){re.escape(anchor)}(?![a-z0-9])", text)
    )


def _query_requires_clarification(
    domain_inference: dict[str, Any],
    query_metadata: dict[str, Any],
) -> bool:
    return bool(
        query_metadata.get("query_too_broad")
        or query_metadata.get("query_requires_confirmation")
        or domain_inference.get("requires_clarification")
    )


def _looks_cross_domain(domain_inference: dict[str, Any]) -> bool:
    candidate_count = int(domain_inference.get("candidate_family_count", 0) or 0)
    family_confidence = float(domain_inference.get("family_confidence", 1) or 0)

    return candidate_count >= 2 and family_confidence < 0.58


def _is_out_of_domain(
    *,
    detected_domain: str | None,
    supported_domains: set[str] | None,
    direct_count: int,
    adjacent_count: int,
) -> bool:
    if not detected_domain or not supported_domains:
        return False

    return (
        detected_domain not in supported_domains
        and direct_count == 0
        and adjacent_count == 0
    )
