from dataclasses import asdict, dataclass, field
from math import sqrt
from typing import Any, Dict, List, Sequence

from planning.candidate_models import CandidateDirection
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_goal_relevance import EmbeddingVector


def _cosine_similarity(
    left: EmbeddingVector,
    right: EmbeddingVector,
) -> float:
    if len(left.values) != len(right.values):
        raise ValueError("Embedding vectors must have equal dimensions.")

    numerator = sum(
        left_value * right_value
        for left_value, right_value in zip(
            left.values,
            right.values,
        )
    )
    left_norm = sqrt(sum(value * value for value in left.values))
    right_norm = sqrt(sum(value * value for value in right.values))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return numerator / (left_norm * right_norm)


def _candidate_support_text(candidate: CandidateDirection) -> str:
    parts = [
        candidate.title.strip(),
        candidate.problem_statement.strip(),
        candidate.target_user.strip(),
        " ".join(step.strip() for step in candidate.core_workflow),
    ]

    return ". ".join(part for part in parts if part)


def _source_support_text(source: EvidenceSource) -> str:
    return ". ".join(
        part
        for part in [
            source.title.strip(),
            source.excerpt.strip(),
        ]
        if part
    )


@dataclass
class CitedSourceAlignment:
    source_id: str
    source_type: str
    support_scope: str
    raw_cosine: float
    normalized_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateEvidenceSupportAssessment:
    candidate_title: str
    citation_integrity: Dict[str, Any]
    direct_citation_count: int
    adjacent_citation_count: int
    uncited_candidate: bool
    cited_source_alignments: List[CitedSourceAlignment] = field(
        default_factory=list
    )
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_title": self.candidate_title,
            "citation_integrity": dict(self.citation_integrity),
            "direct_citation_count": self.direct_citation_count,
            "adjacent_citation_count": self.adjacent_citation_count,
            "uncited_candidate": self.uncited_candidate,
            "cited_source_alignments": [
                alignment.to_dict()
                for alignment in self.cited_source_alignments
            ],
            "warnings": list(self.warnings),
        }


class CandidateEvidenceSupportScorer:
    """
    Shadow-only candidate-to-evidence assessment.

    This records citation validity, source scope, and semantic alignment.
    It does not alter live candidate ranking or selection.
    """

    def __init__(self, encoder: Any):
        self._encoder = encoder

    def assess_candidate(
        self,
        candidate: CandidateDirection,
        brief: EvidenceBrief,
    ) -> CandidateEvidenceSupportAssessment:
        known_sources = {
            source.source_id: source
            for source in brief.sources
        }

        provided_source_ids = list(candidate.source_ids)
        valid_source_ids = [
            source_id
            for source_id in provided_source_ids
            if source_id in known_sources
        ]
        invalid_source_ids = [
            source_id
            for source_id in provided_source_ids
            if source_id not in known_sources
        ]

        warnings: List[str] = []
        uncited_candidate = not provided_source_ids

        if uncited_candidate:
            warnings.append(
                "Candidate has no named evidence sources."
            )

        if invalid_source_ids:
            warnings.append(
                "Candidate cites source IDs outside the evidence brief: "
                + ", ".join(invalid_source_ids)
                + "."
            )

        candidate_embedding = self._encoder.encode_text(
            _candidate_support_text(candidate)
        )

        alignments: List[CitedSourceAlignment] = []

        for source_id in valid_source_ids:
            source = known_sources[source_id]
            source_embedding = self._encoder.encode_text(
                _source_support_text(source)
            )
            raw_cosine = _cosine_similarity(
                candidate_embedding,
                source_embedding,
            )

            alignments.append(
                CitedSourceAlignment(
                    source_id=source.source_id,
                    source_type=source.source_type,
                    support_scope=source.support_scope,
                    raw_cosine=round(raw_cosine, 4),
                    normalized_score=round(
                        max(0.0, min(1.0, (raw_cosine + 1.0) / 2.0)),
                        4,
                    ),
                )
            )

        direct_citation_count = sum(
            1
            for alignment in alignments
            if alignment.support_scope == "direct"
        )
        adjacent_citation_count = sum(
            1
            for alignment in alignments
            if alignment.support_scope == "adjacent_planning"
        )

        if (
            provided_source_ids
            and not direct_citation_count
            and adjacent_citation_count
        ):
            warnings.append(
                "Candidate cites only adjacent planning evidence, not "
                "directly retained evidence."
            )

        return CandidateEvidenceSupportAssessment(
            candidate_title=candidate.title,
            citation_integrity={
                "provided_count": len(provided_source_ids),
                "valid_count": len(valid_source_ids),
                "invalid_count": len(invalid_source_ids),
                "valid_fraction": round(
                    len(valid_source_ids)
                    / len(provided_source_ids),
                    4,
                )
                if provided_source_ids
                else 0.0,
            },
            direct_citation_count=direct_citation_count,
            adjacent_citation_count=adjacent_citation_count,
            uncited_candidate=uncited_candidate,
            cited_source_alignments=alignments,
            warnings=warnings,
        )
