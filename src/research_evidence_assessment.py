from typing import Any, Dict, List, Mapping

from research_evidence_aggregation import aggregate_research_evidence
from research_evidence_confidence import classify_evidence_confidence


def build_evidence_assessment(
    papers: List[Mapping[str, Any]],
    query: str,
    required_anchor_terms: List[str] = None,
) -> Dict[str, Any]:
    """
    Build a traceable evidence assessment for a retrieved research set.

    This combines deterministic aggregation and confidence classification.
    It does not retrieve papers or generate project recommendations.
    """
    normalized_query = str(query or "").strip()

    evidence = aggregate_research_evidence(
        papers,
        query=normalized_query,
        required_anchor_terms=required_anchor_terms,
    )
    confidence = classify_evidence_confidence(evidence)

    return {
        "query": normalized_query,
        "required_anchor_terms": list(required_anchor_terms or []),
        "confidence": confidence,
        "evidence": evidence,
    }
