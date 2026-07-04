import re
from collections import Counter
from typing import Any, Dict, Iterable, List

from planning.planner_models import EvidenceBrief, EvidenceSource


MAX_SOURCES = 12
MAX_EXCERPT_CHARS = 700

# Generic language cleanup only. These are not domain concepts or idea templates.
STOP_WORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "based",
    "between",
    "build",
    "can",
    "for",
    "from",
    "have",
    "into",
    "its",
    "more",
    "not",
    "project",
    "research",
    "system",
    "that",
    "the",
    "their",
    "this",
    "through",
    "using",
    "with",
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)

    return str(value)


def _safe_int(value: Any):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_nonempty(values: Iterable[Any]) -> str:
    for value in values:
        text = _as_text(value).strip()
        if text:
            return text

    return ""


def _source_excerpt(item: Dict[str, Any]) -> str:
    existing_excerpt = _as_text(item.get("excerpt")).strip()

    if existing_excerpt:
        return existing_excerpt[:MAX_EXCERPT_CHARS].strip()

    title = _as_text(item.get("title")).strip()
    body = _first_nonempty(
        [
            item.get("abstract"),
            item.get("content"),
            item.get("readme_excerpt"),
            item.get("selection_reason"),
        ]
    )

    combined = " ".join(part for part in [title, body] if part)
    return combined[:MAX_EXCERPT_CHARS].strip()


def _source_id(item: Dict[str, Any], position: int) -> str:
    return _first_nonempty(
        [
            item.get("source_id"),
            item.get("document_id"),
            item.get("repository_id"),
            item.get("id"),
            item.get("url"),
            item.get("title"),
            f"evidence-{position}",
        ]
    )


def _retrieval_signals(item: Dict[str, Any]) -> Dict[str, float]:
    signals = {}

    for key in [
        "semantic_score",
        "bm25_score",
        "rrf_score",
        "rerank_score",
        "score",
    ]:
        value = _safe_float(item.get(key))

        if value is not None:
            signals[key] = value

    return signals


def _tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[a-z][a-z0-9_-]{2,}", text.lower())
        if token not in STOP_WORDS
    ]


def _recurring_concepts(
    sources: List[EvidenceSource],
    limit: int = 12,
) -> List[str]:
    document_frequency = Counter()

    for source in sources:
        document_frequency.update(set(_tokenize(source.excerpt)))

    recurring = [
        (token, count)
        for token, count in document_frequency.items()
        if count >= 2
    ]

    recurring.sort(key=lambda pair: (-pair[1], pair[0]))
    return [token for token, _ in recurring[:limit]]


def _coverage_warnings(
    sources: List[EvidenceSource],
    source_counts: Dict[str, int],
) -> List[str]:
    warnings = []

    if not sources:
        return ["No usable evidence sources were available."]

    if len(sources) == 1:
        warnings.append(
            "Only one evidence source was available, so cross-source support is limited."
        )

    if source_counts.get("research_paper", 0) == 0:
        warnings.append(
            "No research-paper evidence was included in this brief."
        )

    return warnings


def build_evidence_brief(
    evidence_items: List[Dict[str, Any]],
    user_query: str,
    max_sources: int = MAX_SOURCES,
) -> EvidenceBrief:
    normalized_sources = []
    source_counts = Counter()

    for position, item in enumerate(evidence_items[:max_sources], start=1):
        source_type = _as_text(
            item.get("source_type", "unknown")
        ).strip() or "unknown"

        source = EvidenceSource(
            source_id=_source_id(item, position),
            source_type=source_type,
            title=_as_text(
                item.get("title", "Untitled evidence source")
            ).strip() or "Untitled evidence source",
            excerpt=_source_excerpt(item),
            category=_as_text(item.get("category")).strip() or None,
            url=_as_text(item.get("url")).strip() or None,
            retrieval_rank=_safe_int(item.get("retrieval_rank")),
            retrieval_signals=_retrieval_signals(item),
            support_scope=(
                _as_text(item.get("support_scope")).strip() or "direct"
            ),
            retention_reason=(
                _as_text(item.get("retention_reason")).strip()
            ),
        )

        normalized_sources.append(source)
        source_counts[source_type] += 1

    return EvidenceBrief(
        query=_as_text(user_query).strip(),
        sources=normalized_sources,
        source_counts=dict(source_counts),
        recurring_concepts=_recurring_concepts(normalized_sources),
        coverage_warnings=_coverage_warnings(
            normalized_sources,
            dict(source_counts),
        ),
    )
