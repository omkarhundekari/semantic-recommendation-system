from typing import Any, Dict, List, Mapping, Sequence

from evaluation_pooling import build_union_pool
from research_retrieval_service import retrieve_ranked_evidence


EVALUATION_STRATEGIES = (
    "semantic",
    "bm25",
    "hybrid_rrf",
    "hybrid_reranked",
)


def build_query_candidate_export(
    query_spec: Mapping[str, Any],
    top_k: int,
    candidate_k: int = 50,
) -> Dict[str, Any]:
    """
    Build one evaluation-ready candidate export for a query.

    The exported pool uses document_id as identity. Method provenance is
    retained for later reporting, not for blind labeling.
    """
    query = str(query_spec["query"])

    results_by_method: Dict[str, List[Dict[str, Any]]] = {}

    for strategy in EVALUATION_STRATEGIES:
        results_by_method[strategy] = retrieve_ranked_evidence(
            query=query,
            top_k=top_k,
            strategy=strategy,
            candidate_k=candidate_k,
        )

    pool = build_union_pool(
        results_by_method=results_by_method,
        top_k=top_k,
    )

    method_rankings = {
        strategy: [
            {
                "document_id": result["document_id"],
                "rank": result["retrieval_rank"],
            }
            for result in results
        ]
        for strategy, results in results_by_method.items()
    }

    return {
        "id": str(query_spec["id"]),
        "domain": str(query_spec.get("domain", "") or ""),
        "query": query,
        "candidate_pool": pool,
        "method_rankings": method_rankings,
    }


def build_candidate_export(
    queries: Sequence[Mapping[str, Any]],
    top_k: int,
    candidate_k: int = 50,
) -> Dict[str, Any]:
    return {
        "schema_version": 2,
        "queries": [
            build_query_candidate_export(
                query_spec=query_spec,
                top_k=top_k,
                candidate_k=candidate_k,
            )
            for query_spec in queries
        ],
    }
