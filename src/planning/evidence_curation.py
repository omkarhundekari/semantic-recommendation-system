import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Tuple

from research_query_anchors import (
    extract_required_anchor_terms,
    normalize_text,
)


CURATION_STOP_WORDS = {
    "and",
    "are",
    "build",
    "for",
    "from",
    "into",
    "project",
    "roles",
    "role",
    "system",
    "that",
    "the",
    "this",
    "using",
    "with",
    "engineer",
    "engineers",
    "week",
    "weeks",
    "month",
    "months",
}


@dataclass
class CuratedEvidenceItem:
    item: Dict[str, Any]
    relevance_score: float
    matched_anchor_terms: List[str] = field(default_factory=list)
    matched_query_terms: List[str] = field(default_factory=list)
    retention_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceCurationResult:
    retained: List[CuratedEvidenceItem] = field(default_factory=list)
    dropped: List[CuratedEvidenceItem] = field(default_factory=list)
    required_anchor_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required_anchor_terms": list(self.required_anchor_terms),
            "retained": [
                item.to_dict()
                for item in self.retained
            ],
            "dropped": [
                item.to_dict()
                for item in self.dropped
            ],
            "retained_source_counts": dict(
                Counter(
                    entry.item.get("source_type", "unknown")
                    for entry in self.retained
                )
            ),
        }


def _as_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)

    return str(value)


def _item_text(item: Dict[str, Any]) -> str:
    fields = [
        item.get("title"),
        item.get("abstract"),
        item.get("content"),
        item.get("readme_excerpt"),
        item.get("selection_reason"),
        item.get("tags"),
        item.get("skills"),
        item.get("architecture_signals"),
        item.get("technology_signals"),
        item.get("category"),
    ]

    return " ".join(
        _as_text(field)
        for field in fields
        if _as_text(field).strip()
    )


def _query_terms(query: str) -> List[str]:
    return sorted(
        {
            token
            for token in re.findall(
                r"[a-z][a-z0-9_-]{2,}",
                query.lower(),
            )
            if token not in CURATION_STOP_WORDS
        }
    )


def _retrieval_score(item: Dict[str, Any]) -> float:
    values = []

    for key in [
        "rerank_score",
        "semantic_score",
        "bm25_score",
        "rrf_score",
        "score",
    ]:
        try:
            values.append(float(item.get(key)))
        except (TypeError, ValueError):
            continue

    return max(values, default=0.0)


def _has_retrieval_evidence(item: Dict[str, Any]) -> bool:
    if item.get("retrieval_rank") is not None:
        return True

    return _retrieval_score(item) > 0.0


def _score_item(
    item: Dict[str, Any],
    query_terms: List[str],
    required_anchor_terms: List[str],
) -> CuratedEvidenceItem:
    text = normalize_text(_item_text(item))
    matched_anchors = [
        anchor
        for anchor in required_anchor_terms
        if normalize_text(anchor) in text
    ]

    text_terms = set(text.split())
    matched_terms = [
        term
        for term in query_terms
        if term in text_terms
    ]

    anchor_score = len(matched_anchors) * 10.0
    overlap_score = len(matched_terms) * 2.0
    retrieval_score = min(_retrieval_score(item), 1.0)

    score = anchor_score + overlap_score + retrieval_score

    return CuratedEvidenceItem(
        item=item,
        relevance_score=round(score, 3),
        matched_anchor_terms=matched_anchors,
        matched_query_terms=matched_terms,
    )


def curate_evidence(
    evidence_items: List[Dict[str, Any]],
    user_query: str,
    max_items: int = 6,
) -> EvidenceCurationResult:
    required_anchor_terms = extract_required_anchor_terms(user_query)
    query_terms = _query_terms(user_query)

    scored = [
        _score_item(
            item=item,
            query_terms=query_terms,
            required_anchor_terms=required_anchor_terms,
        )
        for item in evidence_items
    ]

    retained = []
    dropped = []

    for entry in scored:
        has_anchor_support = bool(entry.matched_anchor_terms)
        has_query_support = len(entry.matched_query_terms) >= 2

        if has_anchor_support or has_query_support:
            entry.retention_reason = (
                "Matched registered query anchors."
                if has_anchor_support
                else "Matched multiple meaningful query terms."
            )
            retained.append(entry)
        else:
            entry.retention_reason = (
                "Did not match a registered anchor or enough "
                "meaningful query terms."
            )
            dropped.append(entry)

    retained.sort(
        key=lambda entry: (
            entry.relevance_score,
            len(entry.matched_anchor_terms),
            len(entry.matched_query_terms),
        ),
        reverse=True,
    )

    # Broad queries may not trigger a registered anchor and may use wording
    # that appears only sparsely in individual sources. In that case, retain
    # a small set of retrieval-ranked adjacent sources rather than producing
    # an empty or single-source planning packet. Anchor-driven queries remain
    # strict so unrelated material cannot enter through this fallback.
    if not required_anchor_terms:
        minimum_coverage = min(3, max_items, len(scored))

        if len(retained) < minimum_coverage:
            fallback_candidates = sorted(
                [
                    entry
                    for entry in dropped
                    if (
                        entry.matched_query_terms
                        or _has_retrieval_evidence(entry.item)
                    )
                ],
                key=lambda entry: (
                    entry.relevance_score,
                    _retrieval_score(entry.item),
                ),
                reverse=True,
            )

            for entry in fallback_candidates:
                if len(retained) >= minimum_coverage:
                    break

                entry.retention_reason = (
                    "Retained as retrieval-ranked adjacent evidence because "
                    "the broad query did not provide enough lexical coverage."
                )
                retained.append(entry)
                dropped.remove(entry)

    retained.sort(
        key=lambda entry: (
            entry.relevance_score,
            len(entry.matched_anchor_terms),
            len(entry.matched_query_terms),
        ),
        reverse=True,
    )

    return EvidenceCurationResult(
        retained=retained[:max_items],
        dropped=dropped,
        required_anchor_terms=required_anchor_terms,
    )
