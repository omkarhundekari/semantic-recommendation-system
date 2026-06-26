from typing import Any, Dict, Mapping


def classify_evidence_confidence(
    aggregated_evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Classify research support as strong, limited, or exploratory.

    This policy only evaluates the retrieved evidence set. It does not assess
    feasibility, implementation difficulty, or final project quality.
    """
    paper_count = int(aggregated_evidence.get("paper_count", 0) or 0)
    alignment_summary = aggregated_evidence.get("alignment_summary", {}) or {}
    evidence_tags = aggregated_evidence.get("evidence_tags", {}) or {}

    direct_count = int(alignment_summary.get("direct", 0) or 0)
    adjacent_count = int(alignment_summary.get("adjacent", 0) or 0)
    weak_count = int(alignment_summary.get("weak", 0) or 0)

    direct_is_majority = paper_count > 0 and direct_count > paper_count / 2
    supporting_papers = aggregated_evidence.get("supporting_papers", []) or []
    direct_papers = [
        paper
        for paper in supporting_papers
        if paper.get("alignment") == "direct"
    ]

    if direct_papers:
        direct_evidence_tags = {
            tag
            for paper in direct_papers
            for tag in paper.get("evidence_tags", [])
        }
        has_method_support = "method" in direct_evidence_tags
        has_application_support = "application" in direct_evidence_tags
        support_scope = "direct papers"
    else:
        has_method_support = int(evidence_tags.get("method", 0) or 0) >= 1
        has_application_support = int(evidence_tags.get("application", 0) or 0) >= 1
        support_scope = "the retrieved set"

    if (
        direct_count >= 3
        and direct_is_majority
        and has_method_support
        and has_application_support
    ):
        level = "strong"
        reason = (
            "Strong direct evidence: at least three retrieved papers are "
            "directly aligned with the query, direct evidence is the majority, "
            f"and {support_scope} include both method and application support."
        )
    elif direct_count >= 3 and direct_is_majority:
        level = "limited"
        reason = (
            "Limited direct evidence: the retrieved papers are directly aligned, "
            f"but {support_scope} do not yet include both method and "
            "application support."
        )
    elif direct_count >= 1:
        level = "limited"
        reason = (
            "Limited direct evidence: at least one retrieved paper is directly "
            "aligned, but direct support is not yet broad enough to be strong."
        )
    else:
        level = "exploratory"
        reason = (
            "Exploratory evidence: no direct research support was found in the "
            "retrieved set; available papers are only adjacent or weakly related."
        )

    return {
        "level": level,
        "reason": reason,
        "paper_count": paper_count,
        "direct_paper_count": direct_count,
        "adjacent_paper_count": adjacent_count,
        "weak_paper_count": weak_count,
    }
