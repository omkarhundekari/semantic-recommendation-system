import math
from typing import Dict, List, Mapping, Sequence

from evaluation_coverage import assess_label_coverage


def precision_at_k(relevances: Sequence[int], k: int) -> float:
    values = list(relevances[:k])

    if not values:
        return 0.0

    return sum(value > 0 for value in values) / len(values)


def reciprocal_rank(relevances: Sequence[int]) -> float:
    for rank, relevance in enumerate(relevances, start=1):
        if relevance > 0:
            return 1.0 / rank

    return 0.0


def dcg_at_k(relevances: Sequence[int], k: int) -> float:
    return sum(
        relevance / math.log2(rank + 1)
        for rank, relevance in enumerate(relevances[:k], start=1)
    )


def ndcg_at_k(relevances: Sequence[int], k: int) -> float:
    actual = dcg_at_k(relevances, k)
    ideal = dcg_at_k(sorted(relevances, reverse=True), k)

    if ideal == 0:
        return 0.0

    return actual / ideal


def score_ranking_if_covered(
    ranking: Sequence[Mapping[str, object]],
    labels: Mapping[str, int],
    top_k: int,
) -> Dict[str, object]:
    """
    Score a ranking only when every requested top-K result has a label.
    """
    coverage = assess_label_coverage(
        ranking=ranking,
        labels=labels,
        top_k=top_k,
    )

    if not coverage["eligible"]:
        return {
            **coverage,
            "relevances": None,
            "precision_at_k": None,
            "reciprocal_rank": None,
            "ndcg_at_k": None,
        }

    selected = list(ranking[:top_k])
    relevances = [
        int(labels[str(item["document_id"])])
        for item in selected
    ]

    return {
        **coverage,
        "relevances": relevances,
        "precision_at_k": precision_at_k(relevances, top_k),
        "reciprocal_rank": reciprocal_rank(relevances),
        "ndcg_at_k": ndcg_at_k(relevances, top_k),
    }
