from typing import Any, Dict, List

from bm25_retriever import BM25Retriever
from embedding_search import (
    df,
    document_embeddings,
    documents,
    engine,
)
from reranker import CrossEncoderReranker
from rrf_fusion import reciprocal_rank_fusion
from research_records import build_research_record


_bm25_retriever = None
_reranker = None


def _get_bm25_retriever() -> BM25Retriever:
    global _bm25_retriever

    if _bm25_retriever is None:
        _bm25_retriever = BM25Retriever(documents)

    return _bm25_retriever


def _get_reranker() -> CrossEncoderReranker:
    global _reranker

    if _reranker is None:
        _reranker = CrossEncoderReranker()

    return _reranker


def _document_record(index: int) -> Dict[str, Any]:
    return build_research_record(
        paper=df.iloc[index],
        index=index,
    )


def semantic_retrieve(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    ranked_indices, similarity_scores = engine.search(
        query,
        documents,
        document_embeddings,
    )

    results = []

    for raw_index in ranked_indices[:top_k]:
        index = int(raw_index)
        result = _document_record(index)
        result["semantic_score"] = float(similarity_scores[index].item())
        results.append(result)

    return results


def bm25_retrieve(query: str, top_k: int = 10) -> List[Dict[str, Any]]:
    retriever = _get_bm25_retriever()
    ranked_results = retriever.search(query, top_k=top_k)

    results = []

    for item in ranked_results:
        result = _document_record(int(item["index"]))
        result["bm25_score"] = float(item["score"])
        results.append(result)

    return results


def hybrid_rrf_retrieve(
    query: str,
    top_k: int = 10,
    candidate_k: int = 50,
) -> List[Dict[str, Any]]:
    semantic_candidates = semantic_retrieve(query, top_k=candidate_k)
    bm25_candidates = bm25_retrieve(query, top_k=candidate_k)

    semantic_rank_list = [
        {"index": item["index"]}
        for item in semantic_candidates
    ]
    bm25_rank_list = [
        {"index": item["index"]}
        for item in bm25_candidates
    ]

    fused = reciprocal_rank_fusion(
        [semantic_rank_list, bm25_rank_list]
    )

    semantic_scores = {
        item["index"]: item.get("semantic_score")
        for item in semantic_candidates
    }
    bm25_scores = {
        item["index"]: item.get("bm25_score")
        for item in bm25_candidates
    }

    results = []

    for item in fused[:top_k]:
        index = int(item["index"])
        result = _document_record(index)
        result["rrf_score"] = float(item["rrf_score"])
        result["semantic_score"] = semantic_scores.get(index)
        result["bm25_score"] = bm25_scores.get(index)
        results.append(result)

    return results


def hybrid_reranked_retrieve(
    query: str,
    top_k: int = 10,
    candidate_k: int = 50,
) -> List[Dict[str, Any]]:
    candidates = hybrid_rrf_retrieve(
        query=query,
        top_k=candidate_k,
        candidate_k=candidate_k,
    )

    reranker = _get_reranker()
    reranked = reranker.rerank(query, candidates)

    return reranked[:top_k]
