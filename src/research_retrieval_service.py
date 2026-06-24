from typing import Any, Dict, List

from hybrid_retriever import (
    bm25_retrieve,
    hybrid_reranked_retrieve,
    hybrid_rrf_retrieve,
    semantic_retrieve,
)


SUPPORTED_STRATEGIES = {
    "semantic",
    "bm25",
    "hybrid_rrf",
    "hybrid_reranked",
}


def retrieve_ranked_evidence(
    query: str,
    top_k: int = 10,
    strategy: str = "hybrid_reranked",
    candidate_k: int = 50,
) -> List[Dict[str, Any]]:
    """
    Retrieve ranked research evidence through the canonical retrieval path.

    This is the only entry point that production code and evaluation code
    should use for research-paper retrieval.

    Strategies:
    - semantic
    - bm25
    - hybrid_rrf
    - hybrid_reranked
    """
    normalized_strategy = str(strategy or "").strip().lower()

    if normalized_strategy not in SUPPORTED_STRATEGIES:
        supported = ", ".join(sorted(SUPPORTED_STRATEGIES))
        raise ValueError(
            f"Unsupported retrieval strategy: {strategy}. "
            f"Supported strategies: {supported}."
        )

    if normalized_strategy == "semantic":
        raw_results = semantic_retrieve(query, top_k=top_k)
    elif normalized_strategy == "bm25":
        raw_results = bm25_retrieve(query, top_k=top_k)
    elif normalized_strategy == "hybrid_rrf":
        raw_results = hybrid_rrf_retrieve(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        )
    else:
        raw_results = hybrid_reranked_retrieve(
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
        )

    ranked_results = []

    for rank, result in enumerate(raw_results, start=1):
        enriched_result = dict(result)
        enriched_result["retrieval_strategy"] = normalized_strategy
        enriched_result["retrieval_rank"] = rank
        ranked_results.append(enriched_result)

    return ranked_results
