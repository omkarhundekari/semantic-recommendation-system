import pytest

import research_retrieval_service as service


def test_rejects_unsupported_strategy():
    with pytest.raises(ValueError, match="Unsupported retrieval strategy"):
        service.retrieve_ranked_evidence(
            query="test query",
            strategy="unknown_strategy",
        )


def test_adds_strategy_and_rank_to_semantic_results(monkeypatch):
    monkeypatch.setattr(
        service,
        "semantic_retrieve",
        lambda query, top_k: [
            {"document_id": "arxiv:1111.11111", "title": "First"},
            {"document_id": "arxiv:2222.22222", "title": "Second"},
        ],
    )

    results = service.retrieve_ranked_evidence(
        query="test query",
        top_k=2,
        strategy="semantic",
    )

    assert [result["retrieval_rank"] for result in results] == [1, 2]
    assert all(
        result["retrieval_strategy"] == "semantic"
        for result in results
    )


def test_passes_candidate_k_to_hybrid_reranked(monkeypatch):
    captured = {}

    def fake_hybrid_reranked(query, top_k, candidate_k):
        captured["query"] = query
        captured["top_k"] = top_k
        captured["candidate_k"] = candidate_k
        return [{"document_id": "arxiv:3333.33333", "title": "Paper"}]

    monkeypatch.setattr(
        service,
        "hybrid_reranked_retrieve",
        fake_hybrid_reranked,
    )

    results = service.retrieve_ranked_evidence(
        query="rag question answering",
        top_k=3,
        strategy="hybrid_reranked",
        candidate_k=25,
    )

    assert captured == {
        "query": "rag question answering",
        "top_k": 3,
        "candidate_k": 25,
    }
    assert results[0]["retrieval_rank"] == 1
    assert results[0]["retrieval_strategy"] == "hybrid_reranked"
