from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List


STRONG_DIRECT = "strong_direct"
ADEQUATE_DIRECT = "adequate_direct"
ADJACENT_ONLY = "adjacent_only"
EXPLORATORY = "exploratory"
OUT_OF_DOMAIN = "out_of_domain"
QUERY_TOO_BROAD = "query_too_broad"
CROSS_DOMAIN = "cross_domain"


COVERAGE_NOTES = {
    STRONG_DIRECT: {
        "confidence": "Strong",
        "prefix": "Strongly supported by direct evidence.",
        "warning": None,
    },
    ADEQUATE_DIRECT: {
        "confidence": "Limited",
        "prefix": "Supported by limited direct evidence.",
        "warning": "limited_direct_evidence",
    },
    ADJACENT_ONLY: {
        "confidence": "Exploratory",
        "prefix": "Built from adjacent evidence, not direct support.",
        "warning": "adjacent_evidence_only",
    },
    EXPLORATORY: {
        "confidence": "Exploratory",
        "prefix": "Exploratory direction with sparse evidence.",
        "warning": "low_evidence",
    },
    OUT_OF_DOMAIN: {
        "confidence": "Exploratory",
        "prefix": "Outside the strongest current corpus coverage.",
        "warning": "out_of_domain",
    },
    QUERY_TOO_BROAD: {
        "confidence": "Exploratory",
        "prefix": "Needs a narrower technical direction before strong planning.",
        "warning": "query_too_broad",
    },
    CROSS_DOMAIN: {
        "confidence": "Limited",
        "prefix": "Cross-domain direction; validate each subproblem separately.",
        "warning": "cross_domain_query",
    },
}


def apply_coverage_notes_to_ideas(
    *,
    ideas: List[Dict[str, Any]],
    evidence_coverage: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    if not evidence_coverage:
        return ideas

    coverage_state = str(
        evidence_coverage.get("coverage_state", "")
    ).strip()
    note = COVERAGE_NOTES.get(coverage_state)

    if not note:
        return ideas

    updated_ideas = []

    for idea in ideas:
        updated = deepcopy(idea)

        updated["evidence_confidence"] = note["confidence"]

        updated["evidence_focus_statement"] = _prepend_note(
            prefix=note["prefix"],
            text=updated.get("evidence_focus_statement")
            or updated.get("research_motivation")
            or "",
        )

        updated["research_motivation"] = _prepend_note(
            prefix=note["prefix"],
            text=updated.get("research_motivation") or "",
        )

        warnings = list(updated.get("grounding_warnings", []) or [])
        warning = note.get("warning")

        if warning and warning not in warnings:
            warnings.append(warning)

        updated["grounding_warnings"] = warnings

        updated_ideas.append(updated)

    return updated_ideas


def _prepend_note(*, prefix: str, text: str) -> str:
    clean_text = str(text or "").strip()

    if not clean_text:
        return prefix

    if clean_text.startswith(prefix):
        return clean_text

    return f"{prefix} {clean_text}"
