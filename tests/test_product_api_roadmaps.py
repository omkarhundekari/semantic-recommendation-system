from product_api import build_roadmap


def test_rag_idea_receives_a_rag_specific_problem_definition_stage():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": (
            "Students and small teams need a practical way to inspect "
            "where a RAG pipeline is failing."
        ),
        "mvp_scope": ["Implement a small evaluation workflow."],
        "advanced_extensions": ["Add reranking comparison."],
    }

    roadmap = build_roadmap(idea)

    first_stage = roadmap[0]

    assert first_stage.title == "Define the RAG evaluation question"
    assert first_stage.purpose == (
        "Choose a narrow RAG workflow, a constrained document set, "
        "and measurable evaluation targets."
    )

    roadmap_text = " ".join(
        f"{stage.title} {stage.purpose} {' '.join(stage.tasks)}"
        for stage in roadmap
    ).lower()

    assert "turn the recommendation" not in roadmap_text
    assert "rag" in roadmap_text


def test_project_api_returns_playbook_aware_rag_roadmap_missions():
    from product_api import generate_project_intelligence
    from schemas.product_models import ProjectIntelligenceRequest

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="Build a RAG evaluation project for question answering",
        )
    )

    assert response.status == "ready"
    assert response.resolved_planning_domain == "rag_llm"
    assert response.directions

    roadmap = response.directions[0].roadmap
    roadmap_text = " ".join(
        " ".join(
            [
                stage.objective or "",
                " ".join(stage.commands),
                " ".join(stage.expected_outputs),
                " ".join(stage.validation_checks),
                stage.portfolio_artifact or "",
            ]
        )
        for stage in roadmap
    ).lower()

    assert "retrieval_precision_at_3" in roadmap_text
    assert "data/documents/" in roadmap_text
    assert "data/eval_questions.json" in roadmap_text
    assert "retrieved chunks with source metadata" in roadmap_text
    assert "outputs/retrieval_results.json" in roadmap_text
