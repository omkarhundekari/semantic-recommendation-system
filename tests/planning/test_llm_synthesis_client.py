import json
from pathlib import Path

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    SessionBudgetState,
    decide_llm_routing,
)
from planning.llm_synthesis_client import (
    FakeLLMSynthesisProvider,
    LLMSynthesisRequest,
    synthesize_project_directions,
)
from planning.token_estimation import estimate_tokens_for_prompt


def _load_artifact(relative_path):
    return json.loads(Path(relative_path).read_text())


def _request_for_artifact(relative_path, mode=DEEP_MODE):
    artifact = _load_artifact(relative_path)
    cards = build_evidence_cards_from_artifact(artifact)
    prompt = build_llm_synthesis_prompt(
        user_goal=artifact["query"],
        constraints=artifact["constraints"],
        evidence_cards=cards,
    )
    token_estimate = estimate_tokens_for_prompt(prompt)
    routing_decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=SessionBudgetState(
            calls_remaining=5,
            tokens_remaining=10_000,
            budget_available=True,
        ),
        mode=mode,
        estimated_tokens=token_estimate.estimated_tokens,
    )

    return LLMSynthesisRequest(
        prompt=prompt,
        routing_decision=routing_decision,
        token_estimate=token_estimate,
    )


def test_synthesis_client_parses_valid_fake_provider_response():
    request = _request_for_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )
    provider = FakeLLMSynthesisProvider(
        raw_response_text=json.dumps(
            {
                "project_directions": [
                    {
                        "title": "Evidence Lineage Dashboard",
                        "source_ids": [
                            "paper-owner-aware-lineage",
                            "paper-data-quality-impact",
                        ],
                        "evidence_confidence": "Strong",
                    }
                ],
                "overall_confidence": "Strong",
                "assumptions": [],
                "warnings": [],
            }
        )
    )

    response = synthesize_project_directions(
        request=request,
        provider=provider,
    )

    assert response.provider_name == "fake"
    assert response.model_name == "fake-synthesis-model"
    assert response.parsed_response is not None
    assert response.parsed_response["overall_confidence"] == "Strong"
    assert response.warnings == ()
    assert response.routing_metadata["should_route"] is True
    assert response.token_estimate["estimated_tokens"] > 0


def test_synthesis_client_blocks_when_routing_rejects():
    request = _request_for_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json",
        mode=FAST_MODE,
    )
    provider = FakeLLMSynthesisProvider(
        raw_response_text=json.dumps(
            {
                "project_directions": [],
                "overall_confidence": "Strong",
            }
        )
    )

    response = synthesize_project_directions(
        request=request,
        provider=provider,
    )

    assert response.raw_response_text == ""
    assert response.parsed_response is None
    assert response.warnings == ("routing_decision_blocked_synthesis",)
    assert response.routing_metadata["should_route"] is False


def test_synthesis_client_warns_on_invalid_json_response():
    request = _request_for_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )
    provider = FakeLLMSynthesisProvider(
        raw_response_text="not json"
    )

    response = synthesize_project_directions(
        request=request,
        provider=provider,
    )

    assert response.parsed_response is None
    assert response.warnings == ("invalid_json_response",)


def test_synthesis_client_warns_on_missing_expected_fields():
    request = _request_for_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )
    provider = FakeLLMSynthesisProvider(
        raw_response_text=json.dumps({"hello": "world"})
    )

    response = synthesize_project_directions(
        request=request,
        provider=provider,
    )

    assert response.parsed_response == {"hello": "world"}
    assert "missing_project_directions" in response.warnings
    assert "missing_overall_confidence" in response.warnings


def test_synthesis_request_does_not_leak_manual_review_or_oracle_terms():
    request = _request_for_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    serialized = json.dumps(request.to_dict())

    blocked_terms = [
        "manual_review",
        "oracle",
        "expected_overall_preference",
        "reviewer_confidence",
        "raw_candidates",
        "legacy_planner",
    ]

    for term in blocked_terms:
        assert term not in serialized
