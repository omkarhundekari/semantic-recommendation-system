from planning.query_anchor_direction_adapter import (
    adapt_ideas_to_planning_semantics,
    adapt_ideas_to_query_anchors,
    extract_query_anchors,
)
from query_semantic_projections import (
    build_planning_semantic_projection,
)
from query_semantics import build_query_semantic_snapshot



def _planning_semantics(query: str):
    return build_planning_semantic_projection(
        build_query_semantic_snapshot(query)
    )


def test_extract_query_anchors_preserves_compact_technical_terms():
    assert extract_query_anchors("AR VR education project") == [
        "AR",
        "VR",
        "Education",
    ]


def test_education_titles_preserve_ar_vr_anchors():
    ideas = [
        {
            "project_title": "Student Learning Path Recommendation System",
            "idea_angle": "Build a recommendation workflow.",
            "evidence_focus_statement": "Supported by limited direct evidence.",
        },
        {
            "project_title": "AI Tutor Progress Analytics Dashboard",
            "idea_angle": "Track student progress.",
            "evidence_focus_statement": "Use evidence to scope the dashboard.",
        },
        {
            "project_title": "Course Difficulty Prediction Tool",
            "idea_angle": "Predict course difficulty.",
            "evidence_focus_statement": "Use analytics evidence.",
        },
    ]

    adapted = adapt_ideas_to_query_anchors(
        ideas=ideas,
        query="AR VR education project",
        resolved_domain="education_tech",
    )

    titles = [idea["project_title"] for idea in adapted]

    assert titles == [
        "AR VR Education Learning Explorer",
        "AR VR Education Classroom Prototype",
        "AR VR Education Feedback Dashboard",
    ]

    assert all("AR, VR, Education focus" in idea["idea_angle"] for idea in adapted)


def test_existing_anchor_title_is_not_rewritten():
    ideas = [
        {
            "project_title": "React Frontend Performance Dashboard",
            "idea_angle": "Measure interaction performance.",
            "evidence_focus_statement": "Use frontend evidence.",
        }
    ]

    adapted = adapt_ideas_to_query_anchors(
        ideas=ideas,
        query="React portfolio project",
        resolved_domain="frontend",
    )

    assert adapted[0]["project_title"] == "React Frontend Performance Dashboard"
    assert "React, Portfolio focus" in adapted[0]["idea_angle"]



def test_typed_adapter_uses_canonical_unknown_fallback_in_source_order():
    ideas = [
        {
            "project_title": "Student Learning Path Recommendation System",
            "idea_angle": "Build a recommendation workflow.",
            "evidence_focus_statement": "Supported by evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "AR VR education project"
        ),
        resolved_domain="education_tech",
    )

    assert (
        adapted[0]["project_title"]
        == "AR VR education Learning Explorer"
    )
    assert (
        "AR, VR, education focus"
        in adapted[0]["idea_angle"]
    )


def test_typed_adapter_does_not_render_unresolved_enclosing_duplicate():
    projection = _planning_semantics(
        "AR VR education project"
    )

    # Canonical projection intentionally preserves both the unresolved
    # enclosing phrase and its better-supported constituent concepts.
    assert [
        concept.surface_form
        for concept in projection.presentation_order
    ] == [
        "AR",
        "AR VR education",
        "VR",
        "education",
    ]

    ideas = [
        {
            "project_title": "Student Learning Path Recommendation System",
            "idea_angle": "Build a recommendation workflow.",
            "evidence_focus_statement": "Supported by evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=projection,
        resolved_domain="education_tech",
    )

    assert (
        adapted[0]["project_title"]
        == "AR VR education Learning Explorer"
    )

    assert (
        "AR, VR, education focus"
        in adapted[0]["idea_angle"]
    )


def test_typed_adapter_preserves_unresolved_open_world_phrase_without_supported_alternatives():
    ideas = [
        {
            "project_title": "Experimental System",
            "idea_angle": "Explore the requested direction.",
            "evidence_focus_statement": "Use available evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "Zorvex blenko project"
        ),
        resolved_domain=None,
    )

    assert adapted[0]["project_title"].startswith(
        "Zorvex blenko "
    )

    assert (
        "Zorvex blenko focus"
        in adapted[0]["idea_angle"]
    )


def test_typed_adapter_does_not_promote_skill_held_as_requested_focus():
    ideas = [
        {
            "project_title": "Recommendation System",
            "idea_angle": "Build a focused project.",
            "evidence_focus_statement": "Use available evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "I know React but want an AI project using FastAPI"
        ),
        resolved_domain="ai_ml",
    )

    assert adapted[0]["project_title"].startswith(
        "AI FastAPI "
    )
    assert not adapted[0]["project_title"].startswith(
        "React "
    )
    assert (
        "AI, FastAPI focus"
        in adapted[0]["idea_angle"]
    )


def test_typed_adapter_preserves_role_phrase_and_requested_stack():
    ideas = [
        {
            "project_title": "Portfolio Automation",
            "idea_angle": "Build a portfolio direction.",
            "evidence_focus_statement": "Use relevant evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "cybersecurity analyst portfolio using FastAPI"
        ),
        resolved_domain="cybersecurity",
    )

    assert adapted[0]["project_title"].startswith(
        "cybersecurity analyst FastAPI "
    )
    assert (
        "cybersecurity analyst, FastAPI focus"
        in adapted[0]["idea_angle"]
    )


def test_typed_adapter_preserves_open_world_stack_preference():
    ideas = [
        {
            "project_title": "Experimental System",
            "idea_angle": "Build an experimental direction.",
            "evidence_focus_statement": "Use available evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "build something with ZorvexQL"
        ),
        resolved_domain=None,
    )

    assert adapted[0]["project_title"].startswith(
        "ZorvexQL "
    )
    assert "ZorvexQL focus" in adapted[0]["idea_angle"]


def test_typed_adapter_distinguishes_goal_stack_and_learning_target():
    ideas = [
        {
            "project_title": "Evaluation Workflow",
            "idea_angle": "Build the requested workflow.",
            "evidence_focus_statement": "Use grounded evidence.",
        }
    ]

    adapted = adapt_ideas_to_planning_semantics(
        ideas=ideas,
        planning_semantics=_planning_semantics(
            "I want a RAG app using Qdrant and want to learn Kubernetes"
        ),
        resolved_domain="rag_llm",
    )

    assert adapted[0]["project_title"].startswith(
        "RAG Qdrant Kubernetes "
    )
    assert (
        "RAG, Qdrant, Kubernetes focus"
        in adapted[0]["idea_angle"]
    )
