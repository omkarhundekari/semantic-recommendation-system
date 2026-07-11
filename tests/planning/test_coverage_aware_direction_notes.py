from planning.coverage_aware_direction_notes import (
    apply_coverage_notes_to_ideas,
)


def base_idea():
    return {
        "project_title": "RAG Evaluation Dashboard",
        "idea_angle": "Inspect retrieval quality.",
        "evidence_focus_statement": "Grounded in retrieval evaluation sources.",
        "research_motivation": "Use evidence to evaluate generated answers.",
        "evidence_confidence": "Strong",
        "grounding_warnings": [],
    }


def test_strong_direct_keeps_confident_language():
    ideas = apply_coverage_notes_to_ideas(
        ideas=[base_idea()],
        evidence_coverage={"coverage_state": "strong_direct"},
    )

    idea = ideas[0]

    assert idea["evidence_confidence"] == "Strong"
    assert idea["evidence_focus_statement"].startswith(
        "Strongly supported by direct evidence."
    )
    assert idea["grounding_warnings"] == []


def test_adequate_direct_adds_limited_evidence_caveat():
    ideas = apply_coverage_notes_to_ideas(
        ideas=[base_idea()],
        evidence_coverage={"coverage_state": "adequate_direct"},
    )

    idea = ideas[0]

    assert idea["evidence_confidence"] == "Limited"
    assert idea["evidence_focus_statement"].startswith(
        "Supported by limited direct evidence."
    )
    assert "limited_direct_evidence" in idea["grounding_warnings"]


def test_adjacent_only_marks_direction_exploratory():
    ideas = apply_coverage_notes_to_ideas(
        ideas=[base_idea()],
        evidence_coverage={"coverage_state": "adjacent_only"},
    )

    idea = ideas[0]

    assert idea["evidence_confidence"] == "Exploratory"
    assert idea["evidence_focus_statement"].startswith(
        "Built from adjacent evidence, not direct support."
    )
    assert "adjacent_evidence_only" in idea["grounding_warnings"]


def test_unknown_coverage_state_leaves_ideas_unchanged():
    idea = base_idea()

    ideas = apply_coverage_notes_to_ideas(
        ideas=[idea],
        evidence_coverage={"coverage_state": "unknown"},
    )

    assert ideas == [idea]
