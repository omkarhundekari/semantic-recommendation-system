from typing import Sequence, Set

from planning.semantic_goal_relevance import GoalRelevanceResult


def select_low_margin_candidate_keys(
    results: Sequence[GoalRelevanceResult],
    top_k: int,
    margin_threshold: float,
) -> Set[str]:
    """
    Return top-K embedding candidates whose raw cosine score is within
    margin_threshold of the top embedding score.

    This is an evaluation/shadow policy only. It does not rerank,
    select, or mutate candidates.
    """
    if not results or top_k <= 0:
        return set()

    ranked_results = sorted(
        results,
        key=lambda result: result.trace.raw_cosine,
        reverse=True,
    )
    top_results = ranked_results[:top_k]
    top_score = top_results[0].trace.raw_cosine

    return {
        result.candidate_key
        for result in top_results
        if (
            top_score - result.trace.raw_cosine
        ) <= margin_threshold
    }
