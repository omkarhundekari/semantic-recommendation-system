from typing import Any, Dict, List, Optional

from research_query_anchors import extract_required_anchor_terms
from schemas.decision_trace_models import (
    DetectedSignal,
    IdeaInspiration,
    ImplementationReference,
    ProjectDecisionTrace,
    SupportingPaperEvidence,
)


def _title_key(value: str) -> str:
    return " ".join(
        "".join(character.lower() if character.isalnum() else " " for character in value).split()
    )


def _selected_evidence_title(idea: Dict[str, Any]) -> str:
    return str(
        idea.get("evidence_title")
        or idea.get("based_on_paper")
        or ""
    ).strip()


def _build_supporting_paper(paper: Dict[str, Any]) -> SupportingPaperEvidence:
    return SupportingPaperEvidence(
        document_id=paper["document_id"],
        title=paper["title"],
        category=paper.get("category"),
        retrieval_rank=paper.get("retrieval_rank"),
        alignment=paper.get("alignment", "weak"),
        evidence_tags=paper.get("evidence_tags", []),
        evidence_snippets=paper.get("evidence_snippets", []),
        matched_query_terms=paper.get("matched_query_terms", []),
        matched_query_phrases=paper.get("matched_query_phrases", []),
        matched_required_anchor_terms=paper.get(
            "matched_required_anchor_terms",
            [],
        ),
        alignment_reason=paper.get("reason", ""),
    )


def _build_supporting_papers(
    idea: Dict[str, Any],
    assessment: Dict[str, Any],
) -> List[SupportingPaperEvidence]:
    if idea.get("evidence_source_type") != "research_paper":
        return []

    selected_title = _title_key(_selected_evidence_title(idea))
    if not selected_title:
        return []

    supporting_papers = (
        assessment.get("evidence", {})
        .get("supporting_papers", [])
    )

    return [
        _build_supporting_paper(paper)
        for paper in supporting_papers
        if _title_key(str(paper.get("title", ""))) == selected_title
    ]


def _normalized_evidence_tags(
    assessment: Dict[str, Any],
) -> List[str]:
    raw_tags = (
        assessment.get("evidence", {})
        .get("evidence_tags", {})
    )

    if isinstance(raw_tags, dict):
        return list(raw_tags.keys())

    if isinstance(raw_tags, list):
        return raw_tags

    return []


def _build_detected_signals(
    assessment: Dict[str, Any],
) -> List[DetectedSignal]:
    raw_signals = (
        assessment.get("evidence", {})
        .get("signals", {})
    )

    detected_signals = []

    for group, signals_by_name in raw_signals.items():
        for name, signal in signals_by_name.items():
            detected_signals.append(
                DetectedSignal(
                    group=group,
                    name=name,
                    paper_count=signal.get("paper_count", 0),
                    supporting_document_ids=signal.get(
                        "document_ids",
                        [],
                    ),
                )
            )

    return detected_signals


def _build_primary_inspiration(
    idea: Dict[str, Any],
) -> Optional[IdeaInspiration]:
    title = _selected_evidence_title(idea)

    if not title:
        return None

    return IdeaInspiration(
        title=title,
        source_type=idea.get("evidence_source_type", "unknown"),
        url=idea.get("evidence_url") or None,
    )


def _build_implementation_references(
    idea: Dict[str, Any],
) -> List[ImplementationReference]:
    if idea.get("evidence_source_type") != "github_repository":
        return []

    selected_title = _title_key(_selected_evidence_title(idea))

    return [
        ImplementationReference(
            title=source["title"],
            source_type=source.get("source_type", "unknown"),
            architecture_signals=source.get(
                "architecture_signals",
                [],
            ),
            technology_signals=source.get(
                "technology_signals",
                [],
            ),
            trusted=source.get("trusted", False),
        )
        for source in idea.get("source_contributions", [])
        if _title_key(str(source.get("title", ""))) == selected_title
    ]


def _planning_domain_reason(
    planning_domain: str,
    assessment: Dict[str, Any],
    query: str,
) -> str:
    anchors = assessment.get("required_anchor_terms") or (
        extract_required_anchor_terms(query)
    )

    if (
        planning_domain == "rag_llm"
        and "retrieval augmented generation" in anchors
    ):
        return (
            "Registered query anchors "
            f"({', '.join(anchors)}) selected the rag_llm planning domain."
        )

    return (
        "No specialized anchor policy applied; the planner retained "
        f"the resolved domain '{planning_domain}'."
    )


def _research_support_scope(
    idea: Dict[str, Any],
) -> str:
    source_type = idea.get("evidence_source_type", "")

    if source_type == "research_paper":
        return "idea_specific"

    if source_type in {"github_repository", "project_pattern"}:
        return "mixed"

    return "planning_domain"


def _assumptions(
    idea: Dict[str, Any],
) -> List[str]:
    scope = _research_support_scope(idea)
    assumptions = []

    if scope == "idea_specific":
        assumptions.append(
            "The selected research paper is the idea-specific source, "
            "while the project remains a generated software interpretation "
            "rather than a direct reproduction."
        )
    elif scope == "mixed":
        assumptions.append(
            "The selected implementation or project-pattern reference "
            "informs the build approach, while research support remains "
            "attached to the broader planning domain."
        )
    else:
        assumptions.append(
            "This direction is informed by the research session at the "
            "planning-domain level, not attributed to one specific paper."
        )

    return assumptions


def _evidence_gaps(
    idea: Dict[str, Any],
    assessment: Dict[str, Any],
    supporting_papers: List[SupportingPaperEvidence],
) -> List[str]:
    alignment_summary = (
        assessment.get("evidence", {})
        .get("alignment_summary", {})
    )

    gaps = [
        (
            "Deterministic feasibility assessment is deferred to "
            "Phase 2 of the decision-trace roadmap."
        )
    ]

    if (
        idea.get("evidence_source_type") == "research_paper"
        and not supporting_papers
    ):
        gaps.append(
            "The selected research paper was not present in the focused "
            "assessment evidence, so it should not be treated as "
            "independently verified direct support."
        )

    if alignment_summary.get("adjacent", 0) > 0:
        gaps.append(
            "Some retrieved papers are adjacent rather than directly "
            "aligned with the query."
        )

    if alignment_summary.get("weak", 0) > 0:
        gaps.append(
            "Some retrieved papers have weak alignment and should not "
            "be treated as direct support."
        )

    return gaps


def build_project_decision_trace(
    idea: Dict[str, Any],
    idea_id: str,
    assessment: Dict[str, Any],
    query: str,
) -> ProjectDecisionTrace:
    confidence = assessment.get("confidence", {})
    planning_domain = idea.get("detected_domain", "general")
    supporting_papers = _build_supporting_papers(
        idea,
        assessment,
    )

    rationale = (
        idea.get("evidence_focus_statement")
        or idea.get("research_motivation")
        or idea.get("evidence_driven_angle")
        or idea.get("idea_angle")
        or "No idea-specific rationale was available."
    )

    return ProjectDecisionTrace(
        idea_id=idea_id,
        idea_title=idea.get("project_title", idea_id),
        research_support_scope=_research_support_scope(idea),
        supporting_papers=supporting_papers,
        evidence_tags=_normalized_evidence_tags(assessment),
        detected_signals=_build_detected_signals(assessment),
        buildable_gap=idea.get(
            "evidence_buildable_gap",
            "No explicit buildable gap was identified.",
        ),
        confidence_level=confidence.get("level", "exploratory"),
        confidence_reason=confidence.get(
            "reason",
            "No confidence explanation was available.",
        ),
        planning_domain=planning_domain,
        planning_domain_reason=_planning_domain_reason(
            planning_domain,
            assessment,
            query,
        ),
        idea_specific_rationale=rationale,
        primary_inspiration=_build_primary_inspiration(idea),
        implementation_references=_build_implementation_references(idea),
        assumptions=_assumptions(idea),
        evidence_gaps=_evidence_gaps(
            idea,
            assessment,
            supporting_papers,
        ),
    )
