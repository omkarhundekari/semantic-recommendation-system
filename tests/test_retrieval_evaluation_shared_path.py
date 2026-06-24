import retrieval_evaluation as evaluation


def test_retrieve_for_mode_uses_shared_retrieval_service(monkeypatch):
    captured = {}

    def fake_retrieve_ranked_evidence(
        query,
        top_k,
        strategy,
        candidate_k=50,
    ):
        captured["query"] = query
        captured["top_k"] = top_k
        captured["strategy"] = strategy
        captured["candidate_k"] = candidate_k
        return [{"document_id": "arxiv:2009.08553"}]

    monkeypatch.setattr(
        evaluation,
        "retrieve_ranked_evidence",
        fake_retrieve_ranked_evidence,
    )

    results = evaluation.retrieve_for_mode(
        mode_name="hybrid_reranked",
        query="rag question answering",
        top_k=5,
    )

    assert results == [{"document_id": "arxiv:2009.08553"}]
    assert captured == {
        "query": "rag question answering",
        "top_k": 5,
        "strategy": "hybrid_reranked",
        "candidate_k": 50,
    }
