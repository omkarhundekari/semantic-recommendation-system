from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


DIRECT_SUPPORT_SCOPE = "direct"
ADJACENT_SUPPORT_SCOPE = "adjacent_planning"

LEXICALLY_SUPPORTED = "lexically_supported"
ADJACENT_CONTEXT_ONLY = "adjacent_context_only"
POSSIBLE_MISMATCH = "possible_mismatch"
INVALID_SOURCE_ID = "invalid_source_id"

RELEVANCE_SIGNAL_BY_STATUS = {
    LEXICALLY_SUPPORTED: "plausible",
    ADJACENT_CONTEXT_ONLY: "weak",
    POSSIBLE_MISMATCH: "suspicious",
    INVALID_SOURCE_ID: "suspicious",
}


@dataclass(frozen=True)
class EvidenceCard:
    source_id: str
    source_type: str
    title: str
    support_scope: str
    evidence_confidence: str
    key_excerpt: str
    specific_method_or_technique: str | None
    specific_dataset_or_benchmark: str | None
    specific_implementation_signal: str | None
    grounding_warning: str | None
    relevance_signal: str
    relevance_statuses: tuple[str, ...]
    linked_candidate_titles: tuple[str, ...]
    user_facing_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_cards_from_artifact(
    artifact: dict[str, Any],
) -> list[EvidenceCard]:
    shadow = artifact["v2_shadow"]
    sources = shadow["report"]["evidence_brief"]["sources"]
    traces = shadow.get("candidate_source_relevance", [])
    warnings = shadow.get("quality_warnings", {}).get("warnings", [])

    source_traces = _group_traces_by_source_id(traces)
    source_warnings = _group_warnings_by_source_id(warnings)

    has_research_paper = any(
        source.get("source_type") == "research_paper"
        for source in sources
    )
    artifact_confidence = _infer_artifact_evidence_confidence(
        sources=sources,
        has_research_paper=has_research_paper,
    )

    cards = []
    for source in sources:
        source_id = source["source_id"]
        traces_for_source = source_traces.get(source_id, [])
        warning_codes = source_warnings.get(source_id, [])

        support_scope = source.get("support_scope", "")
        source_type = source.get("source_type", "")

        relevance_statuses = tuple(
            sorted({
                trace.get("relevance_status", "")
                for trace in traces_for_source
                if trace.get("relevance_status")
            })
        )
        linked_candidate_titles = tuple(
            sorted({
                trace.get("candidate_title", "")
                for trace in traces_for_source
                if trace.get("candidate_title")
            })
        )

        grounding_warning = _select_grounding_warning(
            support_scope=support_scope,
            source_type=source_type,
            relevance_statuses=relevance_statuses,
            warning_codes=warning_codes,
            has_research_paper=has_research_paper,
        )
        relevance_signal = _select_relevance_signal(relevance_statuses)

        key_terms = _collect_trace_terms(traces_for_source)
        excerpt = _clean_excerpt(
            title=source.get("title", ""),
            excerpt=source.get("excerpt", ""),
        )

        cards.append(
            EvidenceCard(
                source_id=source_id,
                source_type=source_type,
                title=source.get("title", ""),
                support_scope=support_scope,
                evidence_confidence=_infer_card_evidence_confidence(
                    artifact_confidence=artifact_confidence,
                    support_scope=support_scope,
                    grounding_warning=grounding_warning,
                ),
                key_excerpt=excerpt,
                specific_method_or_technique=_extract_specific_signal(
                    title=source.get("title", ""),
                    excerpt=excerpt,
                    key_terms=key_terms,
                    preferred_terms=(
                        "lineage",
                        "timeline",
                        "correlation",
                        "retrieval",
                        "agent",
                        "drift",
                        "dependency",
                        "ownership",
                    ),
                ),
                specific_dataset_or_benchmark=_extract_dataset_or_benchmark(excerpt),
                specific_implementation_signal=_extract_specific_signal(
                    title=source.get("title", ""),
                    excerpt=excerpt,
                    key_terms=key_terms,
                    preferred_terms=(
                        "dashboard",
                        "postgresql",
                        "react",
                        "python",
                        "codeowners",
                        "logs",
                        "metrics",
                        "traces",
                        "metadata",
                        "repository",
                        "dependency",
                    ),
                ),
                grounding_warning=grounding_warning,
                relevance_signal=relevance_signal,
                relevance_statuses=relevance_statuses,
                linked_candidate_titles=linked_candidate_titles,
                user_facing_explanation=_build_user_facing_explanation(
                    source=source,
                    grounding_warning=grounding_warning,
                    relevance_signal=relevance_signal,
                    linked_candidate_titles=linked_candidate_titles,
                ),
            )
        )

    return cards


def build_evidence_card_payload_from_artifact(
    artifact: dict[str, Any],
) -> dict[str, Any]:
    cards = build_evidence_cards_from_artifact(artifact)
    return {
        "fixture_id": artifact["artifact_identity"]["fixture_id"],
        "artifact_id": artifact["artifact_identity"]["artifact_id"],
        "evidence_cards": [card.to_dict() for card in cards],
        "card_count": len(cards),
    }


def _group_traces_by_source_id(
    traces: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        grouped.setdefault(trace["source_id"], []).append(trace)
    return grouped


def _group_warnings_by_source_id(
    warnings: list[dict[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for warning in warnings:
        code = warning.get("code", "")
        candidates = warning.get("details", {}).get("candidates", [])
        if not candidates and code:
            grouped.setdefault("__global__", []).append(code)
        for candidate in candidates:
            for source_id in candidate.get("source_ids", []):
                grouped.setdefault(source_id, []).append(code)
    return grouped


def _infer_artifact_evidence_confidence(
    sources: list[dict[str, Any]],
    has_research_paper: bool,
) -> str:
    direct_count = sum(
        1 for source in sources
        if source.get("support_scope") == DIRECT_SUPPORT_SCOPE
    )
    adjacent_count = sum(
        1 for source in sources
        if source.get("support_scope") == ADJACENT_SUPPORT_SCOPE
    )

    if direct_count == 0:
        return "Exploratory"
    if not has_research_paper:
        return "Limited"
    if adjacent_count > 0:
        return "Limited"
    return "Strong"


def _infer_card_evidence_confidence(
    artifact_confidence: str,
    support_scope: str,
    grounding_warning: str | None,
) -> str:
    if support_scope != DIRECT_SUPPORT_SCOPE:
        return "Exploratory"
    if grounding_warning:
        return "Limited"
    return artifact_confidence


def _select_grounding_warning(
    support_scope: str,
    source_type: str,
    relevance_statuses: tuple[str, ...],
    warning_codes: list[str],
    has_research_paper: bool,
) -> str | None:
    if ADJACENT_CONTEXT_ONLY in relevance_statuses:
        return ADJACENT_CONTEXT_ONLY
    if "adjacent_context_only_candidate" in warning_codes:
        return ADJACENT_CONTEXT_ONLY
    if not has_research_paper and source_type != "research_paper":
        return "implementation_only_evidence"
    if support_scope != DIRECT_SUPPORT_SCOPE:
        return "adjacent_evidence"
    return None


def _select_relevance_signal(
    relevance_statuses: tuple[str, ...],
) -> str:
    if not relevance_statuses:
        return "unknown"
    if any(
        RELEVANCE_SIGNAL_BY_STATUS.get(status) == "suspicious"
        for status in relevance_statuses
    ):
        return "suspicious"
    if ADJACENT_CONTEXT_ONLY in relevance_statuses:
        return "weak"
    if LEXICALLY_SUPPORTED in relevance_statuses:
        return "plausible"
    return "unknown"


def _collect_trace_terms(
    traces: list[dict[str, Any]],
) -> tuple[str, ...]:
    terms = []
    for trace in traces:
        terms.extend(trace.get("candidate_source_shared_terms", []))
        terms.extend(trace.get("goal_source_shared_terms", []))
    return tuple(sorted(set(term.lower() for term in terms if term)))


def _clean_excerpt(title: str, excerpt: str) -> str:
    cleaned = " ".join(excerpt.split())
    if title and cleaned.startswith(title):
        cleaned = cleaned[len(title):].strip()
    return cleaned


def _extract_specific_signal(
    title: str,
    excerpt: str,
    key_terms: tuple[str, ...],
    preferred_terms: tuple[str, ...],
) -> str | None:
    lower_excerpt = excerpt.lower()
    lower_title = title.lower()

    matched_terms = [
        term for term in preferred_terms
        if term in lower_excerpt or term in lower_title or term in key_terms
    ]
    if matched_terms:
        return ", ".join(matched_terms[:4])

    if key_terms:
        return ", ".join(key_terms[:5])

    words = [
        word.strip(".,:;()[]").lower()
        for word in excerpt.split()
        if len(word.strip(".,:;()[]")) >= 6
    ]
    return ", ".join(words[:5]) if words else None


def _extract_dataset_or_benchmark(excerpt: str) -> str | None:
    benchmark_markers = ("dataset", "benchmark", "uci", "mnist", "imagenet")
    lower_excerpt = excerpt.lower()
    for marker in benchmark_markers:
        if marker in lower_excerpt:
            return marker
    return None


def _build_user_facing_explanation(
    source: dict[str, Any],
    grounding_warning: str | None,
    relevance_signal: str,
    linked_candidate_titles: tuple[str, ...],
) -> str:
    title = source.get("title", "This source")
    support_scope = source.get("support_scope", "")

    if grounding_warning == ADJACENT_CONTEXT_ONLY:
        return (
            f"{title} is useful planning context, but it is adjacent rather "
            "than direct evidence for the linked recommendation."
        )

    if grounding_warning == "implementation_only_evidence":
        return (
            f"{title} supports implementation planning, but this evidence set "
            "does not include direct research-paper grounding."
        )

    if support_scope == DIRECT_SUPPORT_SCOPE and relevance_signal == "plausible":
        if linked_candidate_titles:
            candidate_text = ", ".join(linked_candidate_titles)
            return (
                f"{title} directly supports the recommendation because it shares "
                f"concrete grounding signals with: {candidate_text}."
            )
        return f"{title} is direct evidence for the user's project direction."

    return (
        f"{title} provides supporting context, but its grounding strength should "
        "be reviewed before treating it as a strong recommendation."
    )
