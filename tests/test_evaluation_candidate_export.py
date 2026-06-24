import evaluation_candidate_export as exporter


def test_builds_document_id_based_candidate_export(monkeypatch):
    def fake_retrieve_ranked_evidence(
        query,
        top_k,
        strategy,
        candidate_k=50,
    ):
        results = {
            "semantic": [
                {
                    "document_id": "arxiv:1111.11111",
                    "retrieval_rank": 1,
                    "title": "Paper A",
                    "content": "Abstract A",
                    "category": "cs.IR",
                    "published": "2024-01-01",
                    "url": "https://arxiv.org/abs/1111.11111v1",
                    "source": "arXiv",
                }
            ],
            "bm25": [
                {
                    "document_id": "arxiv:2222.22222",
                    "retrieval_rank": 1,
                    "title": "Paper B",
                    "content": "Abstract B",
                    "category": "cs.CL",
                    "published": "2024-02-01",
                    "url": "https://arxiv.org/abs/2222.22222v1",
                    "source": "arXiv",
                }
            ],
            "hybrid_rrf": [
                {
                    "document_id": "arxiv:1111.11111",
                    "retrieval_rank": 1,
                    "title": "Paper A",
                    "content": "Abstract A",
                    "category": "cs.IR",
                    "published": "2024-01-01",
                    "url": "https://arxiv.org/abs/1111.11111v1",
                    "source": "arXiv",
                }
            ],
            "hybrid_reranked": [
                {
                    "document_id": "arxiv:3333.33333",
                    "retrieval_rank": 1,
                    "title": "Paper C",
                    "content": "Abstract C",
                    "category": "cs.AI",
                    "published": "2024-03-01",
                    "url": "https://arxiv.org/abs/3333.33333v1",
                    "source": "arXiv",
                }
            ],
        }

        return results[strategy]

    monkeypatch.setattr(
        exporter,
        "retrieve_ranked_evidence",
        fake_retrieve_ranked_evidence,
    )

    result = exporter.build_query_candidate_export(
        {
            "id": "rag_01",
            "domain": "ai_ml",
            "query": "RAG question answering",
        },
        top_k=1,
    )

    assert result["id"] == "rag_01"
    assert result["domain"] == "ai_ml"

    assert [item["document_id"] for item in result["candidate_pool"]] == [
        "arxiv:1111.11111",
        "arxiv:2222.22222",
        "arxiv:3333.33333",
    ]

    assert result["method_rankings"]["semantic"] == [
        {
            "document_id": "arxiv:1111.11111",
            "rank": 1,
        }
    ]

    first_candidate = result["candidate_pool"][0]
    assert first_candidate["provenance"] == [
        {
            "method": "hybrid_rrf",
            "rank": 1,
        },
        {
            "method": "semantic",
            "rank": 1,
        },
    ]


def test_builds_versioned_export_for_multiple_queries(monkeypatch):
    monkeypatch.setattr(
        exporter,
        "build_query_candidate_export",
        lambda query_spec, top_k, candidate_k: {
            "id": query_spec["id"],
        },
    )

    result = exporter.build_candidate_export(
        queries=[
            {"id": "query_01", "query": "first"},
            {"id": "query_02", "query": "second"},
        ],
        top_k=5,
    )

    assert result == {
        "schema_version": 2,
        "queries": [
            {"id": "query_01"},
            {"id": "query_02"},
        ],
    }
