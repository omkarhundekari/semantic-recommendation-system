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
