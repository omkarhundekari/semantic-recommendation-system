import json
from pathlib import Path

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_routing_policy import (
    BUDGET_UNAVAILABLE,
    DEEP_MODE,
    DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE,
    EXPLORATORY_EVIDENCE_ONLY,
    FAST_MODE,
    INTERVIEW_MODE,
    NO_EVIDENCE_CARDS,
    NO_QUERY_ALIGNED_EVIDENCE,
    QUOTA_EXHAUSTED,
    ROUTING_APPROVED,
    TOKEN_BUDGET_EXCEEDED,
    SessionBudgetState,
    decide_llm_routing,
)


def _load_cards(relative_path):
    artifact = json.loads(Path(relative_path).read_text())
    return build_evidence_cards_from_artifact(artifact)


def _healthy_budget():
    return SessionBudgetState(
        calls_remaining=5,
        tokens_remaining=10_000,
        budget_available=True,
    )


def test_routing_rejects_empty_evidence_cards():
    decision = decide_llm_routing(
        evidence_cards=[],
        session_budget=_healthy_budget(),
        mode=DEEP_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == NO_EVIDENCE_CARDS


def test_routing_rejects_exploratory_adjacent_only_evidence():
    cards = _load_cards(
        "data/manual_fixture_artifacts/ambiguous_ai_student_project/"
        "d123d89ceb2742a494f3c6f76a797f09.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=_healthy_budget(),
        mode=DEEP_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == NO_QUERY_ALIGNED_EVIDENCE
    assert decision.evidence_confidence == "Exploratory"
    assert decision.query_aligned_card_count == 0
    assert decision.weak_card_count == 3


def test_routing_uses_deterministic_path_for_strong_fast_mode():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=_healthy_budget(),
        mode=FAST_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE
    assert decision.evidence_confidence == "Strong"
    assert decision.query_aligned_card_count == 3


def test_routing_approves_strong_evidence_for_interview_mode():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=_healthy_budget(),
        mode=INTERVIEW_MODE,
        estimated_tokens=1000,
    )

    assert decision.should_route
    assert decision.reason == ROUTING_APPROVED


def test_routing_approves_limited_mixed_evidence_for_deep_mode():
    cards = _load_cards(
        "data/manual_fixture_artifacts/incident_investigation_broad/"
        "f737ba1de33a41fcab8ff5663795ce5f.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=_healthy_budget(),
        mode=DEEP_MODE,
        estimated_tokens=1000,
    )

    assert decision.should_route
    assert decision.reason == ROUTING_APPROVED
    assert decision.evidence_confidence == "Limited"
    assert decision.query_aligned_card_count == 1
    assert decision.weak_card_count == 2


def test_routing_rejects_when_budget_ledger_is_unavailable_after_value_check():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=SessionBudgetState(
            calls_remaining=5,
            tokens_remaining=10_000,
            budget_available=False,
        ),
        mode=INTERVIEW_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == BUDGET_UNAVAILABLE


def test_routing_rejects_when_call_quota_is_exhausted_after_value_check():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=SessionBudgetState(
            calls_remaining=0,
            tokens_remaining=10_000,
            budget_available=True,
        ),
        mode=INTERVIEW_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == QUOTA_EXHAUSTED


def test_routing_rejects_when_token_budget_is_exceeded_after_value_check():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=SessionBudgetState(
            calls_remaining=5,
            tokens_remaining=500,
            budget_available=True,
        ),
        mode=INTERVIEW_MODE,
        estimated_tokens=1000,
    )

    assert not decision.should_route
    assert decision.reason == TOKEN_BUDGET_EXCEEDED


def test_routing_decision_is_json_serializable():
    cards = _load_cards(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=_healthy_budget(),
        mode=INTERVIEW_MODE,
        estimated_tokens=1000,
    )

    serialized = json.dumps(decision.to_dict())

    assert ROUTING_APPROVED in serialized
    assert "expected_overall_preference" not in serialized
    assert "manual_review" not in serialized
