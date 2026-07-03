from typing import Dict, Sequence, Set

from planning.semantic_goal_relevance import GoalRelevanceResult


def build_low_margin_escalation_details(
    results: Sequence[GoalRelevanceResult],
    top_k: int,
    margin_threshold: float,
) -> Dict[str, Dict[str, object]]:
    """
    Build shadow-only escalation diagnostics from embedding results.

    This does not rerank, select, or mutate candidates.
    """
    if not results:
        return {}

    ranked_results = sorted(
        results,
        key=lambda result: result.trace.raw_cosine,
        reverse=True,
    )
    top_results = ranked_results[:max(top_k, 0)]
    top_score = (
        top_results[0].trace.raw_cosine
        if top_results
        else None
    )

    close_candidate_keys = {
        result.candidate_key
        for result in top_results
        if (
            top_score is not None
            and top_score - result.trace.raw_cosine <= margin_threshold
        )
    }
    has_ambiguity = len(close_candidate_keys) >= 2
    details = {}

    for rank, result in enumerate(ranked_results, start=1):
        margin = (
            round(top_score - result.trace.raw_cosine, 4)
            if top_score is not None
            else None
        )
        escalated = bool(
            has_ambiguity
            and rank <= top_k
            and result.candidate_key in close_candidate_keys
        )

        details[result.candidate_key] = {
            "embedding_rank": rank,
            "top_embedding_margin": margin,
            "cohort_size": len(ranked_results),
            "escalated": escalated,
        }

    return details


def select_low_margin_candidate_keys(
    results: Sequence[GoalRelevanceResult],
    top_k: int,
    margin_threshold: float,
) -> Set[str]:
    """
    Return top-K embedding candidates within margin_threshold of the top
    embedding score.
    """
    details = build_low_margin_escalation_details(
        results=results,
        top_k=top_k,
        margin_threshold=margin_threshold,
    )

    return {
        candidate_key
        for candidate_key, detail in details.items()
        if detail["escalated"]
    }
