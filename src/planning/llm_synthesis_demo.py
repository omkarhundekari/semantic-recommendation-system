from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    INTERVIEW_MODE,
    SessionBudgetState,
    decide_llm_routing,
)
from planning.llm_synthesis_client import (
    FakeLLMSynthesisProvider,
    LLMSynthesisRequest,
    synthesize_project_directions,
)
from planning.openai_synthesis_provider import OpenAISynthesisProvider
from planning.token_estimation import estimate_tokens_for_prompt


DEFAULT_FAKE_RESPONSE = {
    "project_directions": [
        {
            "title": "Dry Run Grounded Project Direction",
            "problem_statement": (
                "This is a dry-run response generated without calling an API."
            ),
            "target_user": "students and early-career engineers",
            "why_this_is_grounded": (
                "The real provider was not called. This verifies the synthesis "
                "pipeline wiring only."
            ),
            "source_ids": [],
            "evidence_confidence": "Limited",
            "grounding_warnings": ["dry_run_fake_response"],
            "mvp_scope": [],
            "advanced_extensions": [],
            "skills_demonstrated": [],
            "resume_bullet": "",
            "interview_talking_points": [],
        }
    ],
    "overall_confidence": "Limited",
    "assumptions": ["Dry run mode was used."],
    "warnings": ["No external LLM call was made."],
}


def build_synthesis_request_from_artifact(
    *,
    artifact: dict[str, Any],
    mode: str,
    calls_remaining: int,
    tokens_remaining: int,
) -> LLMSynthesisRequest:
    evidence_cards = build_evidence_cards_from_artifact(artifact)
    prompt = build_llm_synthesis_prompt(
        user_goal=artifact["query"],
        constraints=artifact["constraints"],
        evidence_cards=evidence_cards,
    )
    token_estimate = estimate_tokens_for_prompt(prompt)
    routing_decision = decide_llm_routing(
        evidence_cards=evidence_cards,
        session_budget=SessionBudgetState(
            calls_remaining=calls_remaining,
            tokens_remaining=tokens_remaining,
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


def run_llm_synthesis_demo(
    *,
    artifact_path: Path,
    mode: str = DEEP_MODE,
    provider_name: str = "fake",
    dry_run: bool = True,
    calls_remaining: int = 5,
    tokens_remaining: int = 10_000,
) -> dict[str, Any]:
    artifact = json.loads(artifact_path.read_text())
    request = build_synthesis_request_from_artifact(
        artifact=artifact,
        mode=mode,
        calls_remaining=calls_remaining,
        tokens_remaining=tokens_remaining,
    )

    provider = _select_provider(
        provider_name=provider_name,
        dry_run=dry_run,
    )

    response = synthesize_project_directions(
        request=request,
        provider=provider,
    )

    return {
        "fixture_id": artifact["artifact_identity"]["fixture_id"],
        "artifact_id": artifact["artifact_identity"]["artifact_id"],
        "mode": mode,
        "provider": provider.provider_name,
        "model": provider.model_name,
        "dry_run": dry_run,
        "api_call_attempted": provider_name == "openai" and not dry_run,
        "routing_decision": request.routing_decision.to_dict(),
        "token_estimate": request.token_estimate.to_dict(),
        "response": response.to_dict(),
    }


def _select_provider(
    *,
    provider_name: str,
    dry_run: bool,
):
    if dry_run:
        return FakeLLMSynthesisProvider(
            raw_response_text=json.dumps(DEFAULT_FAKE_RESPONSE),
            provider_name="fake-dry-run",
            model_name="fake-dry-run-model",
        )

    if provider_name == "fake":
        return FakeLLMSynthesisProvider(
            raw_response_text=json.dumps(DEFAULT_FAKE_RESPONSE),
        )

    if provider_name == "openai":
        return OpenAISynthesisProvider()

    raise ValueError(f"Unknown provider: {provider_name}")


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument(
        "--mode",
        choices=[FAST_MODE, DEEP_MODE, INTERVIEW_MODE],
        default=DEEP_MODE,
    )
    parser.add_argument(
        "--provider",
        choices=["fake", "openai"],
        default="fake",
    )
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--calls-remaining", type=int, default=5)
    parser.add_argument("--tokens-remaining", type=int, default=10_000)
    args = parser.parse_args()

    result = run_llm_synthesis_demo(
        artifact_path=Path(args.artifact_path),
        mode=args.mode,
        provider_name=args.provider,
        dry_run=args.dry_run,
        calls_remaining=args.calls_remaining,
        tokens_remaining=args.tokens_remaining,
    )

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
