import json
from pathlib import Path

from planning.evidence_cards import (
    build_evidence_card_payload_from_artifact,
    build_evidence_cards_from_artifact,
)


def _load_artifact(relative_path):
    return json.loads(Path(relative_path).read_text())


def test_direct_evidence_cards_preserve_specific_grounding_signals():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    cards = build_evidence_cards_from_artifact(artifact)

    assert len(cards) == 3
    assert {card.evidence_confidence for card in cards} == {"Strong"}
    assert {card.grounding_warning for card in cards} == {None}
    assert {card.relevance_signal for card in cards} == {"plausible"}

    impact_card = next(
        card for card in cards
        if card.source_id == "paper-data-quality-impact"
    )

    assert impact_card.support_scope == "direct"
    assert "dashboards" in impact_card.key_excerpt
    assert "owners" in impact_card.key_excerpt
    assert "Data Quality Incident Impact Map" in impact_card.linked_candidate_titles
    assert "directly supports" in impact_card.user_facing_explanation


def test_adjacent_evidence_cards_carry_grounding_warnings():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/ambiguous_ai_student_project/"
        "d123d89ceb2742a494f3c6f76a797f09.json"
    )

    cards = build_evidence_cards_from_artifact(artifact)

    assert len(cards) == 3
    assert {card.evidence_confidence for card in cards} == {"Exploratory"}
    assert {card.grounding_warning for card in cards} == {
        "adjacent_context_only"
    }
    assert {card.relevance_signal for card in cards} == {"weak"}
    assert all(
        "adjacent rather than direct evidence"
        in card.user_facing_explanation
        for card in cards
    )


def test_mixed_incident_cards_preserve_direct_and_adjacent_distinction():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/incident_investigation_broad/"
        "f737ba1de33a41fcab8ff5663795ce5f.json"
    )

    cards = build_evidence_cards_from_artifact(artifact)
    cards_by_source = {card.source_id: card for card in cards}

    assert cards_by_source[
        "repo-incident-review"
    ].grounding_warning is None
    assert cards_by_source[
        "repo-incident-review"
    ].evidence_confidence == "Limited"
    assert cards_by_source[
        "repo-incident-review"
    ].relevance_signal == "plausible"

    assert cards_by_source[
        "paper-incident-timeline"
    ].grounding_warning == "adjacent_context_only"
    assert cards_by_source[
        "paper-observability-correlation"
    ].grounding_warning == "adjacent_context_only"
    assert cards_by_source[
        "paper-incident-timeline"
    ].relevance_signal == "weak"


def test_implementation_only_cards_are_marked_limited_without_research_grounding():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/no_research_paper_implementation_only/"
        "1dd6ca97fd204b7f9d3281db38c828f2.json"
    )

    cards = build_evidence_cards_from_artifact(artifact)

    assert len(cards) == 3
    assert {card.source_type for card in cards} == {"github_repository"}
    assert {card.evidence_confidence for card in cards} == {"Limited"}
    assert {card.grounding_warning for card in cards} == {
        "implementation_only_evidence"
    }
    assert all(
        "does not include direct research-paper grounding"
        in card.user_facing_explanation
        for card in cards
    )


def test_evidence_card_payload_is_llm_ready_without_review_oracle_leakage():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    payload = build_evidence_card_payload_from_artifact(artifact)
    serialized = json.dumps(payload)

    assert payload["fixture_id"] == "deterministic_template_risk"
    assert payload["card_count"] == 3
    assert "evidence_cards" in payload

    assert "expected_overall_preference" not in serialized
    assert "expected_response_quality" not in serialized
    assert "manual_review" not in serialized
    assert "oracle" not in serialized
