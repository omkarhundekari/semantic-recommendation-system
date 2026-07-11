from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List


ANCHOR_STOP_WORDS = {
    "app",
    "application",
    "build",
    "for",
    "idea",
    "ideas",
    "project",
    "system",
    "tool",
}


ANCHOR_ALIASES = {
    "ar": "AR",
    "vr": "VR",
    "rag": "RAG",
    "llm": "LLM",
    "ai": "AI",
    "ml": "ML",
}


def adapt_ideas_to_query_anchors(
    *,
    ideas: List[Dict[str, Any]],
    query: str,
    resolved_domain: str | None = None,
) -> List[Dict[str, Any]]:
    anchors = extract_query_anchors(query)

    if not anchors:
        return ideas

    updated_ideas = []

    for index, idea in enumerate(ideas):
        updated = deepcopy(idea)
        title = str(updated.get("project_title", "") or "")

        if not _title_preserves_strong_anchors(title, anchors):
            updated["project_title"] = _anchored_title(
                title=title,
                anchors=anchors,
                resolved_domain=resolved_domain,
                index=index,
            )

        updated["idea_angle"] = _prepend_anchor_context(
            text=str(updated.get("idea_angle", "") or ""),
            anchors=anchors,
            resolved_domain=resolved_domain,
        )

        updated["evidence_focus_statement"] = _prepend_anchor_context(
            text=str(updated.get("evidence_focus_statement", "") or ""),
            anchors=anchors,
            resolved_domain=resolved_domain,
        )

        updated_ideas.append(updated)

    return updated_ideas


def extract_query_anchors(query: str) -> List[str]:
    raw_tokens = re.findall(r"[a-z][a-z0-9]{1,}", query.lower())

    anchors = []

    for token in raw_tokens:
        if token in ANCHOR_STOP_WORDS:
            continue

        if token in ANCHOR_ALIASES:
            normalized = ANCHOR_ALIASES[token]
        else:
            normalized = token.replace("_", " ").title()

        if normalized not in anchors:
            anchors.append(normalized)

    return anchors[:4]


def _title_preserves_strong_anchors(title: str, anchors: List[str]) -> bool:
    normalized_title = title.lower()
    strong_anchors = [
        anchor
        for anchor in anchors
        if anchor.lower() in {"ar", "vr", "rag", "llm", "ai", "ml", "react"}
    ]

    if strong_anchors:
        return any(
            _anchor_matches_title(anchor, normalized_title)
            for anchor in strong_anchors
        )

    return any(
        _anchor_matches_title(anchor, normalized_title)
        for anchor in anchors
    )


def _anchor_matches_title(anchor: str, normalized_title: str) -> bool:
    normalized_anchor = anchor.strip().lower()

    if not normalized_anchor:
        return False

    if " " in normalized_anchor:
        return normalized_anchor in normalized_title

    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_anchor)}(?![a-z0-9])",
            normalized_title,
        )
    )


def _anchored_title(
    *,
    title: str,
    anchors: List[str],
    resolved_domain: str | None,
    index: int,
) -> str:
    anchor_phrase = " ".join(anchors[:3])

    if resolved_domain == "education_tech":
        options = [
            f"{anchor_phrase} Learning Explorer",
            f"{anchor_phrase} Classroom Prototype",
            f"{anchor_phrase} Feedback Dashboard",
        ]
        return options[index % len(options)]

    if resolved_domain == "frontend":
        return f"{anchor_phrase} Frontend Experience"

    if resolved_domain == "rag_llm":
        return f"{anchor_phrase} Evaluation Studio"

    clean_title = title.strip()

    if clean_title:
        return f"{anchor_phrase} {clean_title}"

    return f"{anchor_phrase} Project Direction"


def _prepend_anchor_context(
    *,
    text: str,
    anchors: List[str],
    resolved_domain: str | None,
) -> str:
    anchor_phrase = ", ".join(anchors[:4])
    domain_phrase = (
        resolved_domain.replace("_", " ")
        if resolved_domain
        else "the requested domain"
    )

    prefix = (
        f"Preserves the user's {anchor_phrase} focus while staying within "
        f"{domain_phrase}."
    )

    clean_text = text.strip()

    if not clean_text:
        return prefix

    if clean_text.startswith(prefix):
        return clean_text

    return f"{prefix} {clean_text}"
