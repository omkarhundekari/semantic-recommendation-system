from project_intelligence import build_project_intelligence


def test_rag_evidence_generates_rag_oriented_project_blueprints():
    evidence_items = [
        {
            "document_id": "arxiv:1111.11111",
            "title": "Retrieval-Augmented Generation for Question Answering",
            "abstract": (
                "We improve retrieval augmented generation for "
                "question answering using retrieval quality evaluation."
            ),
            "content": (
                "Retrieval augmented generation for question answering "
                "with retrieval evaluation and factual grounding."
            ),
            "category": "cs.IR",
            "source_type": "research_paper",
            "retrieval_rank": 1,
        },
        {
            "document_id": "arxiv:2222.22222",
            "title": "Evaluation of RAG Question Answering Systems",
            "abstract": (
                "We evaluate retrieval augmented generation systems "
                "for factual question answering."
            ),
            "content": (
                "RAG systems require retrieval evaluation, answer "
                "grounding, and question answering benchmarks."
            ),
            "category": "cs.CL",
            "source_type": "research_paper",
            "retrieval_rank": 2,
        },
        {
            "document_id": "arxiv:3333.33333",
            "title": "Practical Retrieval-Augmented Generation Applications",
            "abstract": (
                "We study practical retrieval augmented generation "
                "applications for reliable answers."
            ),
            "content": (
                "Practical RAG applications use retrieval, generation, "
                "and answer-quality evaluation."
            ),
            "category": "cs.IR",
            "source_type": "research_paper",
            "retrieval_rank": 3,
        },
    ]

    result = build_project_intelligence(
        evidence_items=evidence_items,
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
        detected_domain="rag_llm",
        max_ideas=3,
    )

    titles = [
        blueprint["project_title"].lower()
        for blueprint in result["idea_blueprints"]
    ]

    assert len(titles) == 3
    assert all(
        "recommendation" not in title
        for title in titles
    )
    assert any(
        "rag" in title or "retrieval" in title
        for title in titles
    )
    assert all(
        blueprint["detected_domain"] == "rag_llm"
        for blueprint in result["idea_blueprints"]
    )


def test_project_idea_generator_preserves_rag_planning_domain():
    from project_idea_generator import generate_project_ideas

    ideas = generate_project_ideas(
        search_results=[
            {
                "document_id": "arxiv:1111.11111",
                "title": "Retrieval-Augmented Generation for Question Answering",
                "content": (
                    "Retrieval augmented generation for question answering "
                    "with retrieval evaluation and factual grounding."
                ),
                "category": "cs.IR",
                "source_type": "research_paper",
            }
        ],
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering for ML engineer roles in 3 weeks"
        ),
        max_ideas=3,
        constraints={},
        detected_domain="rag_llm",
    )

    assert all(idea["detected_domain"] == "rag_llm" for idea in ideas)
