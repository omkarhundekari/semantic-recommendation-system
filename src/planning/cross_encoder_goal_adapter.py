from typing import Any, List, Sequence


class CrossEncoderGoalPairScorer:
    """
    Planning-only adapter for scoring (goal, candidate) text pairs with
    the existing retrieval cross-encoder model.
    """

    def __init__(self, reranker: Any):
        self._reranker = reranker

    def score_pairs(
        self,
        goal_text: str,
        candidate_texts: Sequence[str],
    ) -> List[float]:
        texts = list(candidate_texts)

        if not texts:
            return []

        pairs = [
            [goal_text, candidate_text]
            for candidate_text in texts
        ]

        scores = self._reranker.model.predict(pairs)

        return [float(score) for score in scores]
