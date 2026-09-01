from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Dict, List, Sequence

from query_concept_resolution import ResolutionStatus
from query_concept_understanding import ClauseRole
from query_semantic_projections import (
    PlanningConcept,
    PlanningSemanticProjection,
)


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


def adapt_ideas_to_planning_semantics(
    *,
    ideas: List[Dict[str, Any]],
    planning_semantics: PlanningSemanticProjection,
    resolved_domain: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Adapt generated directions using canonical typed planning semantics.

    Production callers must use this API instead of reparsing the raw
    query. The projection is already the authoritative interpretation of
    the user's concepts and grammatical roles.

    SKILL_HELD concepts remain available to planning but are not promoted
    into project-title/focus language as if the user requested them.

    UNKNOWN concepts are used only as a fallback when no stronger
    intentional concepts are available.
    """
    concepts = _renderable_presentation_concepts(
        _presentation_concepts_for_adapter(
            planning_semantics
        )
    )

    anchors = [
        concept.surface_form.strip()
        for concept in concepts
        if concept.surface_form.strip()
    ][:4]

    return _adapt_ideas_with_anchors(
        ideas=ideas,
        anchors=anchors,
        resolved_domain=resolved_domain,
    )


def _presentation_concepts_for_adapter(
    planning_semantics: PlanningSemanticProjection,
) -> tuple[PlanningConcept, ...]:
    """
    Select which already-interpreted concepts should be emphasized.

    This is presentation policy, not semantic interpretation:
      * requested goals, learning targets, roles, and stack preferences
        are eligible;
      * held skills are preserved by the projection but not promoted;
      * UNKNOWN concepts provide an open-world fallback when no stronger
        intentional concepts exist.

    Source order is preserved by planning_semantics.presentation_order.
    """
    intentional_roles = {
        ClauseRole.GOAL,
        ClauseRole.SKILL_TARGET,
        ClauseRole.ROLE,
        ClauseRole.STACK_PREFERENCE,
    }

    intentional = tuple(
        concept
        for concept in planning_semantics.presentation_order
        if concept.clause_role in intentional_roles
    )

    if intentional:
        return intentional

    return tuple(
        concept
        for concept in planning_semantics.presentation_order
        if concept.clause_role == ClauseRole.UNKNOWN
    )


def _renderable_presentation_concepts(
    concepts: Sequence[PlanningConcept],
) -> tuple[PlanningConcept, ...]:
    """
    Reduce redundant overlapping representations only for prose rendering.

    Canonical semantics deliberately preserves unresolved enclosing
    concepts alongside better-supported contained concepts. The adapter
    must not concatenate those alternative representations as if they
    were independent user requests.

    An unresolved enclosing concept is omitted only when multiple
    same-role, same-segment supported concepts already cover its
    occurrence apart from separator-sized gaps.
    """
    return tuple(
        concept
        for concept in concepts
        if not _redundant_unresolved_container(
            concept,
            concepts,
        )
    )


def _redundant_unresolved_container(
    candidate: PlanningConcept,
    concepts: Sequence[PlanningConcept],
) -> bool:
    if (
        candidate.resolution_status
        != ResolutionStatus.UNRESOLVED
        or candidate.char_span is None
        or candidate.segment_index is None
    ):
        return False

    start, end = candidate.char_span

    contained = [
        other
        for other in concepts
        if (
            other is not candidate
            and other.char_span is not None
            and other.segment_index
            == candidate.segment_index
            and other.clause_role
            == candidate.clause_role
            and other.resolution_status
            != ResolutionStatus.UNRESOLVED
            and start
            <= other.char_span[0]
            and other.char_span[1]
            <= end
            and other.char_span
            != candidate.char_span
        )
    ]

    if len(contained) < 2:
        return False

    if not any(
        other.char_span[0] == start
        for other in contained
    ):
        return False

    if not any(
        other.char_span[1] == end
        for other in contained
    ):
        return False

    intervals = sorted(
        other.char_span
        for other in contained
        if other.char_span is not None
    )

    covered = 0
    current_start, current_end = intervals[0]

    for interval_start, interval_end in intervals[1:]:
        if interval_start <= current_end:
            current_end = max(
                current_end,
                interval_end,
            )
            continue

        covered += current_end - current_start
        current_start, current_end = (
            interval_start,
            interval_end,
        )

    covered += current_end - current_start

    uncovered = (end - start) - covered

    # Contiguous concepts in the source naturally leave separator
    # characters such as spaces between their occurrence spans.
    return uncovered <= len(contained) - 1


def adapt_ideas_to_query_anchors(
    *,
    ideas: List[Dict[str, Any]],
    query: str,
    resolved_domain: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Legacy compatibility path.

    Production orchestration must use adapt_ideas_to_planning_semantics()
    so semantic intent is not independently reconstructed from raw text.
    """
    return _adapt_ideas_with_anchors(
        ideas=ideas,
        anchors=extract_query_anchors(query),
        resolved_domain=resolved_domain,
    )


def _adapt_ideas_with_anchors(
    *,
    ideas: List[Dict[str, Any]],
    anchors: Sequence[str],
    resolved_domain: str | None,
) -> List[Dict[str, Any]]:
    anchors = [
        str(anchor).strip()
        for anchor in anchors
        if str(anchor).strip()
    ][:4]

    if not anchors:
        return ideas

    updated_ideas = []

    for index, idea in enumerate(ideas):
        updated = deepcopy(idea)
        title = str(updated.get("project_title", "") or "")

        if not _title_preserves_strong_anchors(
            title,
            list(anchors),
        ):
            updated["project_title"] = _anchored_title(
                title=title,
                anchors=list(anchors),
                resolved_domain=resolved_domain,
                index=index,
            )

        updated["idea_angle"] = _prepend_anchor_context(
            text=str(updated.get("idea_angle", "") or ""),
            anchors=list(anchors),
            resolved_domain=resolved_domain,
        )

        updated["evidence_focus_statement"] = _prepend_anchor_context(
            text=str(
                updated.get(
                    "evidence_focus_statement",
                    "",
                )
                or ""
            ),
            anchors=list(anchors),
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
