from dataclasses import asdict, dataclass
from typing import List, Sequence

from planning.candidate_models import CandidateDirection
from planning.semantic_goal_relevance import TextEncoder


def build_diversity_text(candidate: CandidateDirection) -> str:
    return " ".join(
        [
            candidate.title,
            candidate.problem_statement,
            candidate.target_user,
            " ".join(candidate.core_workflow),
            " ".join(candidate.mvp_scope),
        ]
    )


@dataclass(frozen=True)
class CandidateDiversityPair:
    candidate_a_title: str
    candidate_b_title: str
    raw_cosine: float
    flagged: bool

    def to_dict(self) -> dict:
        data = asdict(self)
        data["raw_cosine"] = round(self.raw_cosine, 4)
        return data


@dataclass(frozen=True)
class CandidateDiversityTrace:
    similarity_threshold: float
    pairwise_similarity: List[CandidateDiversityPair]
    passed: bool

    def to_dict(self) -> dict:
        return {
            "similarity_threshold": self.similarity_threshold,
            "pairwise_similarity": [
                pair.to_dict()
                for pair in self.pairwise_similarity
            ],
            "passed": self.passed,
        }


class SemanticCandidateDiversityScorer:
    def __init__(self, encoder: TextEncoder):
        self._encoder = encoder

    def assess_candidates(
        self,
        candidates: Sequence[CandidateDirection],
        similarity_threshold: float = 0.82,
    ) -> CandidateDiversityTrace:
        candidate_list = list(candidates)
        embeddings = [
            self._encoder.encode_text(build_diversity_text(candidate))
            for candidate in candidate_list
        ]

        pairs = []

        for left_index in range(len(candidate_list)):
            for right_index in range(left_index + 1, len(candidate_list)):
                raw_cosine = embeddings[left_index].cosine_similarity(
                    embeddings[right_index]
                )
                pairs.append(
                    CandidateDiversityPair(
                        candidate_a_title=candidate_list[left_index].title,
                        candidate_b_title=candidate_list[right_index].title,
                        raw_cosine=raw_cosine,
                        flagged=raw_cosine >= similarity_threshold,
                    )
                )

        return CandidateDiversityTrace(
            similarity_threshold=similarity_threshold,
            pairwise_similarity=pairs,
            passed=not any(pair.flagged for pair in pairs),
        )
