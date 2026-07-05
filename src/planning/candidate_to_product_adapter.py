from typing import Any, Dict, List, Optional

from planning.candidate_models import CandidateDirection
from planning.candidate_provenance import CandidateProvenance
from planning.planner_models import EvidenceBrief, EvidenceSource


def _deduplicate(items: List[str]) -> List[str]:
    seen = set()
    result = []

    for item in items:
        clean_item = str(item).strip()
        key = clean_item.lower()

        if clean_item and key not in seen:
            seen.add(key)
            result.append(clean_item)

    return result


def _known_cited_sources(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
) -> List[EvidenceSource]:
    sources_by_id = {
        source.source_id: source
        for source in brief.sources
    }

    return [
        sources_by_id[source_id]
        for source_id in candidate.source_ids
        if source_id in sources_by_id
    ]


def _select_primary_source(
    cited_sources: List[EvidenceSource],
) -> Optional[EvidenceSource]:
    direct_sources = [
        source
        for source in cited_sources
        if source.support_scope == "direct"
    ]

    if direct_sources:
        return direct_sources[0]

    return cited_sources[0] if cited_sources else None


def _build_advanced_extensions(
    candidate: CandidateDirection,
) -> List[str]:
    extensions = [
        (
            "Add an evaluation view that tracks the MVP success metrics "
            "across representative runs."
        ),
        (
            "Add a failure-case review workflow and document the "
            "prototype's known limitations."
        ),
    ]

    if candidate.success_metrics:
        extensions[0] = (
            "Add an evaluation view for: "
            + candidate.success_metrics[0].strip()
        )

    return _deduplicate(extensions)


def adapt_candidate_to_product_idea(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
    detected_domain: str,
    target_roles: Optional[List[str]] = None,
    planner_provenance: Optional[CandidateProvenance] = None,
) -> Dict[str, Any]:
    """
    Convert a validated planner candidate into the legacy product idea shape.

    This adapter does not score, verify, repair, or apply constraints. Those
    stages remain owned by the deterministic production pipeline.
    """
    cited_sources = _known_cited_sources(candidate, brief)
    primary_source = _select_primary_source(cited_sources)

    source_contributions = [
        {
            "source_id": source.source_id,
            "title": source.title,
            "source_type": source.source_type,
            "support_scope": source.support_scope,
        }
        for source in cited_sources
    ]

    return {
        "project_title": candidate.title,
        "idea_angle": (
            candidate.problem_statement.strip()
            + " Built for "
            + candidate.target_user.strip()
            + "."
        ),
        "detected_domain": detected_domain,
        "evidence_buildable_gap": candidate.problem_statement.strip(),
        "evidence_focus_statement": candidate.evidence_relationship.strip(),
        "evidence_driven_angle": candidate.evidence_relationship.strip(),
        "evidence_project_opportunity": candidate.problem_statement.strip(),
        "research_motivation": candidate.evidence_relationship.strip(),
        "mvp_scope": _deduplicate(list(candidate.mvp_scope)),
        "advanced_extensions": _build_advanced_extensions(candidate),
        "suggested_tech_stack": _deduplicate(
            list(candidate.suggested_stack)
        ),
        "target_roles": _deduplicate(list(target_roles or [])),
        "extracted_skills": _deduplicate(
            list(candidate.suggested_stack)
        ),
        "source_contributions": source_contributions,
        "planner_candidate_source_ids": list(candidate.source_ids),
        "planner_candidate_assumptions": _deduplicate(
            list(candidate.assumptions)
        ),
        "planner_candidate_success_metrics": _deduplicate(
            list(candidate.success_metrics)
        ),
        "planner_candidate_workflow": _deduplicate(
            list(candidate.core_workflow)
        ),
        "evidence_title": (
            primary_source.title if primary_source else ""
        ),
        "evidence_source_type": (
            primary_source.source_type if primary_source else ""
        ),
        "evidence_url": (
            primary_source.url if primary_source else ""
        ),
        "research_category": (
            primary_source.category if primary_source else None
        ),
        "based_on_paper": (
            primary_source.title if primary_source else ""
        ),
        **(
            {
                "planner_provenance": planner_provenance.to_dict(),
            }
            if planner_provenance is not None
            else {}
        ),
    }
