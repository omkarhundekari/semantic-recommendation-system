import json
from pathlib import Path

import pytest

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.token_estimation import (
    estimate_llm_synthesis_prompt_tokens,
    estimate_tokens_for_prompt,
    estimate_tokens_for_sections,
    estimate_tokens_for_text,
    is_within_token_budget,
)


def _load_cards(relative_path):
    artifact = json.loads(Path(relative_path).read_text())
    return build_evidence_cards_from_artifact(artifact)


def _load_artifact(relative_path):
    return json.loads(Path(relative_path).read_text())


def test_text_token_estimation_uses_safety_multiplier():
    estimate = estimate_tokens_for_text(
        "abcd" * 100,
        chars_per_token=4,
        safety_multiplier=1.25,
    )

    assert estimate == 125


def test_section_token_estimation_reports_largest_sections():
    estimate = estimate_tokens_for_sections(
        {
            "small": "abc",
            "large": "x" * 400,
            "medium": "y" * 120,
        },
        chars_per_token=4,
        safety_multiplier=1.0,
        largest_section_count=2,
    )

    assert estimate.estimated_tokens == 131
    assert estimate.raw_character_count == 523
    assert estimate.section_token_estimates["large"] == 100
    assert estimate.largest_sections == ("large", "medium")


def test_llm_synthesis_prompt_estimate_accepts_evidence_cards():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    estimate = estimate_llm_synthesis_prompt_tokens(
        user_goal=(
            "Build a project that helps support engineers understand downstream "
            "dashboard and owner impact after a data-quality incident."
        ),
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["Python", "PostgreSQL"],
        },
        evidence_cards=cards,
        mode="deep",
        system_instruction=(
            "Generate grounded project directions using only the provided evidence cards."
        ),
        output_schema={
            "candidates": [
                {
                    "title": "string",
                    "source_ids": ["string"],
                    "mvp_scope": ["string"],
                }
            ]
        },
    )

    assert estimate.estimated_tokens > 0
    assert estimate.section_token_estimates["evidence_cards"] > 0
    assert "evidence_cards" in estimate.largest_sections
    assert is_within_token_budget(estimate, token_budget=10_000)


def test_prompt_estimate_payload_does_not_include_review_oracle_terms():
    cards = _load_cards(
        "data/manual_fixture_artifacts/ambiguous_ai_student_project/"
        "d123d89ceb2742a494f3c6f76a797f09.json"
    )

    estimate = estimate_llm_synthesis_prompt_tokens(
        user_goal="Build an AI project for students.",
        constraints={"time_available": "3 weeks"},
        evidence_cards=cards,
        mode="deep",
        system_instruction="Generate grounded project directions.",
        output_schema={"candidates": []},
    )

    serialized = json.dumps(estimate.to_dict())

    assert "expected_overall_preference" not in serialized
    assert "expected_response_quality" not in serialized
    assert "manual_review" not in serialized
    assert "oracle" not in serialized


def test_token_budget_check_rejects_over_budget_estimate():
    estimate = estimate_tokens_for_sections(
        {"prompt": "x" * 1000},
        chars_per_token=4,
        safety_multiplier=1.0,
    )

    assert estimate.estimated_tokens == 250
    assert not is_within_token_budget(estimate, token_budget=249)
    assert is_within_token_budget(estimate, token_budget=250)


def test_token_estimation_rejects_invalid_parameters():
    with pytest.raises(ValueError):
        estimate_tokens_for_text("abc", chars_per_token=0)

    with pytest.raises(ValueError):
        estimate_tokens_for_text("abc", safety_multiplier=0)

    with pytest.raises(ValueError):
        estimate_tokens_for_sections(
            {"prompt": "abc"},
            largest_section_count=0,
        )

    estimate = estimate_tokens_for_sections({"prompt": "abc"})
    with pytest.raises(ValueError):
        is_within_token_budget(estimate, token_budget=-1)



def test_token_estimation_accepts_structured_prompt_contract():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )
    cards = build_evidence_cards_from_artifact(artifact)
    prompt = build_llm_synthesis_prompt(
        user_goal=artifact["query"],
        constraints=artifact["constraints"],
        evidence_cards=cards,
    )

    estimate = estimate_tokens_for_prompt(prompt)

    assert estimate.estimated_tokens > 0
    assert estimate.section_token_estimates["evidence_cards"] > 0
    assert "evidence_cards" in estimate.largest_sections
    assert estimate.section_token_estimates["output_schema"] > 0
