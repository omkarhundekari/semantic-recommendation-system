import json
from pathlib import Path

import pytest

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.llm_routing_policy import (
    DEEP_MODE,
    SessionBudgetState,
    decide_llm_routing,
)
from planning.llm_synthesis_client import (
    LLMSynthesisRequest,
    synthesize_project_directions,
)
from planning.openai_synthesis_provider import (
    DEFAULT_OPENAI_MODEL,
    OpenAIProviderConfigurationError,
    OpenAISynthesisProvider,
    _extract_response_text,
)
from planning.token_estimation import estimate_tokens_for_prompt


class FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "output_text": json.dumps(
                {
                    "project_directions": [
                        {
                            "title": "Grounded Direction",
                            "source_ids": ["paper-owner-aware-lineage"],
                            "evidence_confidence": "Strong",
                        }
                    ],
                    "overall_confidence": "Strong",
                    "assumptions": [],
                    "warnings": [],
                }
            )
        }


class FakeOpenAIClient:
    def __init__(self):
        self.responses = FakeResponses()


def _load_artifact(relative_path):
    return json.loads(Path(relative_path).read_text())


def _request():
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
    token_estimate = estimate_tokens_for_prompt(prompt)
    routing_decision = decide_llm_routing(
        evidence_cards=cards,
        session_budget=SessionBudgetState(
            calls_remaining=5,
            tokens_remaining=10_000,
            budget_available=True,
        ),
        mode=DEEP_MODE,
        estimated_tokens=token_estimate.estimated_tokens,
    )
    return LLMSynthesisRequest(
        prompt=prompt,
        routing_decision=routing_decision,
        token_estimate=token_estimate,
    )


def test_openai_provider_uses_responses_api_with_structured_prompt():
    client = FakeOpenAIClient()
    provider = OpenAISynthesisProvider(client=client)

    raw_text = provider.synthesize(_request())

    payload = json.loads(raw_text)
    assert payload["overall_confidence"] == "Strong"

    call = client.responses.calls[0]
    assert call["model"] == DEFAULT_OPENAI_MODEL
    assert call["temperature"] == 0.2
    assert call["max_output_tokens"] == 2500

    messages = call["input"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "# Evidence Cards" in messages[1]["content"]
    assert "paper-owner-aware-lineage" in messages[1]["content"]


def test_openai_provider_integrates_with_synthesis_client():
    provider = OpenAISynthesisProvider(client=FakeOpenAIClient())

    response = synthesize_project_directions(
        request=_request(),
        provider=provider,
    )

    assert response.provider_name == "openai"
    assert response.model_name == DEFAULT_OPENAI_MODEL
    assert response.parsed_response is not None
    assert response.parsed_response["overall_confidence"] == "Strong"
    assert response.warnings == ()


def test_openai_provider_requires_api_key_when_no_client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAISynthesisProvider(client=None)

    with pytest.raises(OpenAIProviderConfigurationError):
        provider._build_client()


def test_extract_response_text_supports_output_text_dict():
    response = {
        "output_text": '{"overall_confidence":"Strong"}',
    }

    assert _extract_response_text(response) == '{"overall_confidence":"Strong"}'


def test_extract_response_text_rejects_unknown_shape():
    with pytest.raises(ValueError):
        _extract_response_text(object())



def test_openai_provider_can_read_model_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.4-mini")
    provider = OpenAISynthesisProvider(
        configured_model_name=None,
        client=FakeOpenAIClient(),
    )

    provider.synthesize(_request())

    call = provider.client.responses.calls[0]
    assert call["model"] == "gpt-5.4-mini"
