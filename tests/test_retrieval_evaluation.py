from retrieval_evaluation import (
    ndcg_at_k,
    precision_at_k,
    reciprocal_rank,
)


def test_precision_at_k_counts_relevant_results():
    assert precision_at_k([2, 1, 0, 0, 2], 5) == 0.6


def test_precision_at_k_handles_empty_values():
    assert precision_at_k([], 5) == 0.0


def test_reciprocal_rank_uses_first_relevant_result():
    assert reciprocal_rank([0, 0, 2, 1]) == 1 / 3


def test_reciprocal_rank_returns_zero_without_relevance():
    assert reciprocal_rank([0, 0, 0]) == 0.0


def test_ndcg_rewards_better_ranked_relevance():
    strong = ndcg_at_k([2, 1, 0, 0], 4)
    weak = ndcg_at_k([0, 0, 2, 1], 4)

    assert strong > weak
