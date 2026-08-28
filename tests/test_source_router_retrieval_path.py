import source_router


def test_source_router_uses_shared_hybrid_retrieval(monkeypatch):
    calls = []

    def fake_retrieve_ranked_evidence(
        query,
        top_k,
        strategy,
        candidate_k=50,
    ):
        calls.append(
            {
                "query": query,
                "top_k": top_k,
                "strategy": strategy,
            }
        )
        return [
            {
                "document_id": "arxiv:2009.08553",
                "title": "Example research paper",
                "url": "https://arxiv.org/abs/2009.08553v4",
                "source": "arXiv",
            }
        ]

    monkeypatch.setattr(
        source_router,
        "retrieve_ranked_evidence",
        fake_retrieve_ranked_evidence,
    )
    monkeypatch.setattr(
        source_router,
        "search_project_corpus",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        source_router,
        "search_github_project_corpus",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        source_router,
        "infer_domain_from_evidence",
        lambda evidence, intent_hints=None: {
            "inferred_focus": "general",
        },
    )

    source_router.retrieve_evidence(
        user_query="original query",
        top_k=2,
    )

    assert calls == [
        {
            "query": "original query",
            "top_k": 6,
            "strategy": "hybrid_rrf",
        },
        {
            "query": "original query",
            "top_k": 6,
            "strategy": "hybrid_rrf",
        },
    ]


def test_source_router_exposes_actual_broad_query_without_legacy_expansion(
    monkeypatch,
):
    monkeypatch.setattr(
        source_router,
        "retrieve_ranked_evidence",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        source_router,
        "search_project_corpus",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        source_router,
        "search_github_project_corpus",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        source_router,
        "infer_domain_from_evidence",
        lambda evidence, intent_hints=None: {
            "inferred_focus": "general",
        },
    )

    payload = source_router.retrieve_evidence(
        user_query="Build an AI project using React",
        top_k=2,
    )

    assert payload["expanded_query"] == (
        "Build an AI project using React"
    )
    assert payload["focused_query"] == (
        "Build an AI project using React"
    )
