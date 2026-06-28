from project_idea_generator import select_evidence_for_focus


def test_rag_idea_does_not_select_unrelated_movie_pattern():
    evidence_items = [
        {
            "title": "Movie Recommendation System with Explanation Layer",
            "source_type": "project_pattern",
            "tags": "recommendation, explainability",
            "skills": "Python, dashboards",
        },
        {
            "title": "RAG Evaluation and Grounding Workbench",
            "source_type": "github_repository",
            "architecture_signals": (
                "retrieval_and_search, evaluation_and_monitoring"
            ),
            "technology_signals": "Python, FastAPI",
        },
        {
            "title": (
                "Retrieval-Augmented Generation Evaluation "
                "for Question Answering"
            ),
            "source_type": "research_paper",
            "abstract": (
                "This study evaluates retrieval quality, answer grounding, "
                "and citation coverage in RAG systems."
            ),
        },
    ]

    selected = select_evidence_for_focus(
        evidence_items=evidence_items,
        focus_type="buildable_gap",
        fallback_index=0,
        planning_domain="rag_llm",
        project_title="RAG Evaluation Studio",
        idea_angle=(
            "Evaluate retrieval quality, grounding, and citation coverage."
        ),
    )

    assert selected["title"] != (
        "Movie Recommendation System with Explanation Layer"
    )
    assert selected["source_type"] in {
        "github_repository",
        "research_paper",
    }


def test_selector_keeps_source_preference_when_candidates_are_relevant():
    evidence_items = [
        {
            "title": "RAG Product Pattern",
            "source_type": "project_pattern",
            "tags": "rag, retrieval, evaluation",
        },
        {
            "title": "RAG Evaluation Repository",
            "source_type": "github_repository",
            "architecture_signals": "retrieval_and_search",
        },
    ]

    selected = select_evidence_for_focus(
        evidence_items=evidence_items,
        focus_type="buildable_gap",
        fallback_index=0,
        planning_domain="rag_llm",
        project_title="RAG Evaluation Studio",
        idea_angle="Build retrieval evaluation workflows.",
    )

    assert selected["source_type"] == "project_pattern"


def test_selector_falls_back_to_source_order_when_no_candidate_is_relevant():
    evidence_items = [
        {
            "title": "Movie Recommendation System",
            "source_type": "project_pattern",
        },
        {
            "title": "Generic Repository",
            "source_type": "github_repository",
        },
    ]

    selected = select_evidence_for_focus(
        evidence_items=evidence_items,
        focus_type="buildable_gap",
        fallback_index=1,
        planning_domain="rag_llm",
        project_title="RAG Evaluation Studio",
        idea_angle="Evaluate retrieval quality.",
    )

    assert selected["source_type"] == "project_pattern"
