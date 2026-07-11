from planning.query_anchor_direction_adapter import (
    adapt_ideas_to_query_anchors,
    extract_query_anchors,
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
