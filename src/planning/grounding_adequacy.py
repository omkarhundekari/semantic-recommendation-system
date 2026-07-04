from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from planning.candidate_models import CandidateDirection
from planning.evidence_support import CandidateEvidenceSupportAssessment
from planning.planner_models import EvidenceBrief


class GroundingAdequacy(str, Enum):
    CITED_WITH_DIRECT_SCOPE = "cited_with_direct_scope"
    CITED_ONLY_ADJACENT = "cited_only_adjacent"
    UNCITED_COVERED = "uncited_covered"
    UNCITED_SPARSE = "uncited_sparse"
    INVALID_CITATIONS = "invalid_citations"


@dataclass
class GroundingAdequacyTrace:
    candidate_title: str
    adequacy_class: GroundingAdequacy
    cited_source_ids: List[str]
    cited_source_scopes: List[str]
    cited_alignment_scores: List[float]
    min_cited_alignment: Optional[float]
    max_cited_alignment: Optional[float]
    direct_sources_in_brief: int
    uncited_direct_sources: List[str]
    adequacy_reason: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["adequacy_class"] = self.adequacy_class.value
        return data


def assess_grounding_adequacy(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
    assessment: CandidateEvidenceSupportAssessment,
) -> GroundingAdequacyTrace:
    direct_source_ids = [
        source.source_id
        for source in brief.sources
        if source.support_scope == "direct"
    ]

    alignments = list(assessment.cited_source_alignments)
    cited_source_ids = [
        alignment.source_id
        for alignment in alignments
    ]
    cited_source_scopes = [
        alignment.support_scope
        for alignment in alignments
    ]
    cited_alignment_scores = [
        alignment.raw_cosine
        for alignment in alignments
    ]
    uncited_direct_sources = [
        source_id
        for source_id in direct_source_ids
        if source_id not in cited_source_ids
    ]

    invalid_count = int(
        assessment.citation_integrity.get("invalid_count", 0) or 0
    )
    valid_count = int(
        assessment.citation_integrity.get("valid_count", 0) or 0
    )

    if invalid_count:
        adequacy_class = GroundingAdequacy.INVALID_CITATIONS
        adequacy_reason = (
            "Candidate includes one or more source IDs outside the "
            "evidence brief."
        )
    elif not candidate.source_ids:
        if direct_source_ids:
            adequacy_class = GroundingAdequacy.UNCITED_COVERED
            adequacy_reason = (
                "Candidate cites no sources even though directly retained "
                "evidence is available in the brief."
            )
        else:
            adequacy_class = GroundingAdequacy.UNCITED_SPARSE
            adequacy_reason = (
                "Candidate cites no sources and the brief contains no "
                "directly retained evidence."
            )
    elif valid_count and assessment.direct_citation_count:
        adequacy_class = GroundingAdequacy.CITED_WITH_DIRECT_SCOPE
        adequacy_reason = (
            "Candidate cites at least one directly retained evidence source."
        )
    else:
        adequacy_class = GroundingAdequacy.CITED_ONLY_ADJACENT
        adequacy_reason = (
            "Candidate cites valid sources, but none are directly retained "
            "evidence sources."
        )

    return GroundingAdequacyTrace(
        candidate_title=candidate.title,
        adequacy_class=adequacy_class,
        cited_source_ids=cited_source_ids,
        cited_source_scopes=cited_source_scopes,
        cited_alignment_scores=cited_alignment_scores,
        min_cited_alignment=(
            min(cited_alignment_scores)
            if cited_alignment_scores
            else None
        ),
        max_cited_alignment=(
            max(cited_alignment_scores)
            if cited_alignment_scores
            else None
        ),
        direct_sources_in_brief=len(direct_source_ids),
        uncited_direct_sources=uncited_direct_sources,
        adequacy_reason=adequacy_reason,
    )
