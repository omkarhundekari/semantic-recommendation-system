from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from planning.llm_prompt_builder import LLMSynthesisPrompt
from planning.llm_routing_policy import LLMRoutingDecision
from planning.token_estimation import TokenEstimate


@dataclass(frozen=True)
class LLMSynthesisRequest:
    prompt: LLMSynthesisPrompt
    routing_decision: LLMRoutingDecision
    token_estimate: TokenEstimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt.to_dict(),
            "routing_decision": self.routing_decision.to_dict(),
            "token_estimate": self.token_estimate.to_dict(),
        }


@dataclass(frozen=True)
class LLMSynthesisResponse:
    provider_name: str
    model_name: str
    raw_response_text: str
    parsed_response: dict[str, Any] | None
    warnings: tuple[str, ...]
    routing_metadata: dict[str, Any]
    token_estimate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMSynthesisProvider(Protocol):
    provider_name: str
    model_name: str

    def synthesize(
        self,
        request: LLMSynthesisRequest,
    ) -> str:
        ...


@dataclass(frozen=True)
class FakeLLMSynthesisProvider:
    raw_response_text: str
    provider_name: str = "fake"
    model_name: str = "fake-synthesis-model"

    def synthesize(
        self,
        request: LLMSynthesisRequest,
    ) -> str:
        return self.raw_response_text


def synthesize_project_directions(
    *,
    request: LLMSynthesisRequest,
    provider: LLMSynthesisProvider,
) -> LLMSynthesisResponse:
    if not request.routing_decision.should_route:
        return LLMSynthesisResponse(
            provider_name=provider.provider_name,
            model_name=provider.model_name,
            raw_response_text="",
            parsed_response=None,
            warnings=("routing_decision_blocked_synthesis",),
            routing_metadata=request.routing_decision.to_dict(),
            token_estimate=request.token_estimate.to_dict(),
        )

    raw_response_text = provider.synthesize(request)
    parsed_response, warnings = _parse_json_response(raw_response_text)

    return LLMSynthesisResponse(
        provider_name=provider.provider_name,
        model_name=provider.model_name,
        raw_response_text=raw_response_text,
        parsed_response=parsed_response,
        warnings=warnings,
        routing_metadata=request.routing_decision.to_dict(),
        token_estimate=request.token_estimate.to_dict(),
    )


def _parse_json_response(
    raw_response_text: str,
) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    try:
        parsed = json.loads(raw_response_text)
    except json.JSONDecodeError:
        return None, ("invalid_json_response",)

    if not isinstance(parsed, dict):
        return None, ("json_response_not_object",)

    warnings = []
    if "project_directions" not in parsed:
        warnings.append("missing_project_directions")
    if "overall_confidence" not in parsed:
        warnings.append("missing_overall_confidence")

    return parsed, tuple(warnings)
