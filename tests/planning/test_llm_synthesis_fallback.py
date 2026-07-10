import json
from pathlib import Path

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_synthesis_fallback import (
    build_deterministic_synthesis_fallback,
    should_use_deterministic_fallback,
)


ARTIFACT_PATH = Path(
    "data/manual_fixture_artifacts/deterministic_template_risk/"
    "1bc94b0f56984302922f13d42dcb2a2e.json"
)

ADJACENT_ARTIFACT_PATH = Path(
    "data/manual_fixture_artifacts/ambiguous_ai_student_project/"
    "d123d89ceb2742a494f3c6f76a797f09.json"
)


def _cards(path):
    artifact = json.loads(path.read_text())
    return build_evidence_cards_from_artifact(artifact)


def test_should_use_deterministic_fallback_when_validation_missing_or_invalid():
    assert should_use_deterministic_fallback(None)
    assert should_use_deterministic_fallback({"is_valid": False})
    assert not should_use_deterministic_fallback({"is_valid": True})


def test_deterministic_fallback_returns_three_scoped_directions():
    fallback = build_deterministic_synthesis_fallback(
        evidence_cards=_cards(ARTIFACT_PATH),
        validation={
            "is_valid": False,
            "errors": ["project_direction_0_missing_source_ids"],
            "failure_categories": ["grounding_failure"],
        },
    )

    directions = fallback["project_directions"]

    assert fallback["synthesis_source"] == "deterministic_fallback"
    assert fallback["overall_confidence"] == "Strong"
    assert len(directions) == 3
    assert [direction["scope_level"] for direction in directions] == [
        "easy",
        "medium",
        "hard",
    ]
    assert [direction["build_type"] for direction in directions] == [
        "quick_build",
        "resume_mvp",
        "flagship_extension",
    ]
    assert [direction["estimated_time"] for direction in directions] == [
        "1-2 days",
        "3-5 days",
        "1-2 weeks",
    ]
    assert directions[0]["source_ids"] == [
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
        "repo-dashboard-impact",
    ]
    assert any("grounding_failure" in warning for warning in fallback["warnings"])


def test_deterministic_fallback_preserves_adjacent_evidence_warnings():
    fallback = build_deterministic_synthesis_fallback(
        evidence_cards=_cards(ADJACENT_ARTIFACT_PATH),
        validation={"is_valid": False},
    )

    assert fallback["overall_confidence"] == "Exploratory"
    assert "adjacent_context_only" in fallback["warnings"]
    assert all(
        "adjacent_context_only" in direction["grounding_warnings"]
        for direction in fallback["project_directions"]
    )


def test_deterministic_fallback_cites_only_available_evidence_card_sources():
    cards = _cards(ARTIFACT_PATH)
    valid_source_ids = {card.source_id for card in cards}

    fallback = build_deterministic_synthesis_fallback(
        evidence_cards=cards,
        validation={"is_valid": False},
    )

    for direction in fallback["project_directions"]:
        assert set(direction["source_ids"]) <= valid_source_ids
