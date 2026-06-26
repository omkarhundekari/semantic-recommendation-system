import re
from typing import Any, Dict, Mapping


STOPWORDS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "into",
    "using",
    "use",
    "based",
    "system",
    "systems",
}


def tokenize(text: Any) -> set:
    normalized = str(text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)

    return {
        token
        for token in tokens
        if len(token) >= 3 and token not in STOPWORDS
    }


def build_query_phrases(text: Any) -> list:
    tokens = re.findall(r"[a-z0-9]+", str(text or "").lower())
    phrases = []
    segment = []

    def add_segment_phrases(words: list) -> None:
        for size in (3, 2):
            for index in range(len(words) - size + 1):
                phrase = " ".join(words[index:index + size])

                if phrase not in phrases:
                    phrases.append(phrase)

    for token in tokens:
        if token in STOPWORDS:
            add_segment_phrases(segment)
            segment = []
            continue

        if len(token) >= 3:
            segment.append(token)

    add_segment_phrases(segment)

    return phrases


def normalize_phrase_text(text: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def classify_evidence_alignment(
    query: str,
    paper: Mapping[str, Any],
    required_anchor_terms: list = None,
) -> Dict[str, Any]:
    """
    Classify paper alignment with a user query using transparent term overlap.

    This is evidence alignment only. It does not determine feasibility,
    recommendation quality, or confidence.
    """
    query_terms = tokenize(query)
    paper_text = " ".join(
        [
            str(paper.get("title", "") or ""),
            str(paper.get("abstract", paper.get("content", "")) or ""),
        ]
    )
    paper_terms = tokenize(paper_text)

    matched_query_terms = sorted(query_terms.intersection(paper_terms))
    normalized_paper_text = normalize_phrase_text(paper_text)
    matched_query_phrases = [
        phrase
        for phrase in build_query_phrases(query)
        if phrase in normalized_paper_text
    ]

    normalized_required_anchor_terms = sorted(
        {
            normalize_phrase_text(anchor)
            for anchor in (required_anchor_terms or [])
            if normalize_phrase_text(anchor)
        }
    )
    matched_required_anchor_terms = [
        anchor
        for anchor in normalized_required_anchor_terms
        if anchor in normalized_paper_text
    ]

    if len(matched_query_terms) >= 3:
        alignment = "direct"
        reason = "The paper matches at least three meaningful query terms."
    elif len(matched_query_terms) >= 2:
        alignment = "adjacent"
        reason = "The paper matches two meaningful query terms but lacks fuller coverage."
    else:
        alignment = "weak"
        reason = "The paper has fewer than two meaningful query-term matches."

    if (
        alignment == "direct"
        and normalized_required_anchor_terms
        and len(matched_required_anchor_terms)
        != len(normalized_required_anchor_terms)
    ):
        alignment = "adjacent"
        reason = (
            "The paper has broad query overlap but does not match every "
            "required query anchor."
        )

    return {
        "alignment": alignment,
        "matched_query_terms": matched_query_terms,
        "matched_query_phrases": matched_query_phrases,
        "matched_required_anchor_terms": matched_required_anchor_terms,
        "reason": reason,
    }
