from dataclasses import dataclass
from typing import Any, List, Sequence

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.goal_text_builder import (
    build_candidate_text,
    build_goal_text,
)


@dataclass(frozen=True)
class CrossEncoderGoalRelevanceResult:
    candidate_title: str
    raw_score: float
    goal_text_used: str
    candidate_text_used: str


class CrossEncoderGoalRelevanceScorer:
    """
    Planning-only semantic precision scorer.

    This does not rank, select, or mutate candidates. It only scores
    goal/candidate pairs in the original candidate order.
    """

    def __init__(self, pair_scorer: Any):
        self._pair_scorer = pair_scorer

    def score_candidates(
        self,
        request: CandidateGenerationRequest,
        candidates: Sequence[CandidateDirection],
    ) -> List[CrossEncoderGoalRelevanceResult]:
        candidate_list = list(candidates)

        if not candidate_list:
            return []

        goal_text = build_goal_text(request)
        candidate_texts = [
            build_candidate_text(candidate)
            for candidate in candidate_list
        ]

        raw_scores = self._pair_scorer.score_pairs(
            goal_text=goal_text,
            candidate_texts=candidate_texts,
        )

        if len(raw_scores) != len(candidate_list):
            raise ValueError(
                "Cross-encoder scorer returned a score count that does "
                "not match the candidate count."
            )

        return [
            CrossEncoderGoalRelevanceResult(
                candidate_title=candidate.title,
                raw_score=float(raw_score),
                goal_text_used=goal_text,
                candidate_text_used=candidate_text,
            )
            for candidate, candidate_text, raw_score in zip(
                candidate_list,
                candidate_texts,
                raw_scores,
            )
        ]
