from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_prompt_builder import build_llm_synthesis_prompt
from planning.llm_synthesis_fallback import (
    build_deterministic_synthesis_fallback,
    should_use_deterministic_fallback,
)
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
from planning.llm_synthesis_output_validator import (
    validate_saved_synthesis_output,
    write_synthesis_validation_report,
)
from planning.openai_synthesis_provider import OpenAISynthesisProvider
from planning.token_estimation import estimate_tokens_for_prompt


DEFAULT_FAKE_RESPONSE = {
    "project_directions": [
        {
            "scope_level": "easy",
            "build_type": "quick_build",
            "estimated_time": "1-2 days",
            "title": "Dry Run Quick Build Direction",
            "problem_statement": (
                "This is a dry-run quick-build response generated without "
                "calling an API."
            ),
            "target_user": "students and early-career engineers",
            "why_this_is_grounded": (
                "The real provider was not called. This verifies the scoped "
                "synthesis pipeline wiring only."
            ),
            "source_ids": [],
            "evidence_confidence": "Limited",
            "grounding_warnings": ["dry_run_fake_response"],
            "mvp_scope": ["Verify routing, prompt, and response parsing."],
            "advanced_extensions": ["Replace fake provider with OpenAI provider."],
            "skills_demonstrated": ["LLM pipeline wiring"],
            "resume_bullet": "Built a dry-run path for scoped LLM synthesis validation.",
            "interview_talking_points": ["Explain safe dry-run provider testing."],
        },
        {
            "scope_level": "medium",
            "build_type": "resume_mvp",
            "estimated_time": "3-5 days",
            "title": "Dry Run Resume MVP Direction",
            "problem_statement": (
                "This is a dry-run resume-MVP response generated without "
                "calling an API."
            ),
            "target_user": "students and early-career engineers",
            "why_this_is_grounded": (
                "The real provider was not called. This verifies that the "
                "medium scoped output contract is present."
            ),
            "source_ids": [],
            "evidence_confidence": "Limited",
            "grounding_warnings": ["dry_run_fake_response"],
            "mvp_scope": ["Verify scoped fields and JSON structure."],
            "advanced_extensions": ["Add validator coverage for saved outputs."],
            "skills_demonstrated": ["Structured output validation"],
            "resume_bullet": "Built a scoped synthesis contract with dry-run validation.",
            "interview_talking_points": ["Explain schema-first LLM integration."],
        },
        {
            "scope_level": "hard",
            "build_type": "flagship_extension",
            "estimated_time": "1-2 weeks",
            "title": "Dry Run Flagship Extension Direction",
            "problem_statement": (
                "This is a dry-run flagship-extension response generated "
                "without calling an API."
            ),
            "target_user": "students and early-career engineers",
            "why_this_is_grounded": (
                "The real provider was not called. This verifies that the "
                "hard scoped output contract is present."
            ),
            "source_ids": [],
            "evidence_confidence": "Limited",
            "grounding_warnings": ["dry_run_fake_response"],
            "mvp_scope": ["Verify end-to-end synthesis demo behavior."],
            "advanced_extensions": ["Run one real provider smoke test."],
            "skills_demonstrated": ["Provider abstraction", "LLM readiness reporting"],
            "resume_bullet": "Implemented a provider-safe LLM synthesis demo path.",
            "interview_talking_points": ["Explain fake-provider testing before paid calls."],
        },
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
    output_path: Path | None = None,
    validation_report_output_path: Path | None = None,
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

    result = {
        "run_metadata": {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "artifact_path": str(artifact_path),
        },
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

    if output_path is not None:
        write_synthesis_demo_output(result, output_path)
        validation = validate_saved_synthesis_output(
            output_path=output_path,
            artifact_path=artifact_path,
        )
        validation_dict = validation.to_dict()
        result["saved_output_validation"] = validation_dict

        if should_use_deterministic_fallback(validation_dict):
            fallback = build_deterministic_synthesis_fallback(
                evidence_cards=build_evidence_cards_from_artifact(artifact),
                validation=validation_dict,
            )
            result["final_synthesis"] = {
                "source": "deterministic_fallback",
                "parsed_response": fallback,
                "fallback_used": True,
                "fallback_reason": "saved_output_validation_failed",
            }
        else:
            result["final_synthesis"] = {
                "source": "llm",
                "parsed_response": result["response"]["parsed_response"],
                "fallback_used": False,
                "fallback_reason": "",
            }

        if validation_report_output_path is not None:
            write_synthesis_validation_report(
                validation=validation,
                output_path=validation_report_output_path,
            )
            result["validation_report_output_path"] = str(
                validation_report_output_path
            )

        write_synthesis_demo_output(result, output_path)

    return result


def write_synthesis_demo_output(
    result: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))
    return output_path


def build_default_output_path(
    *,
    fixture_id: str,
    artifact_id: str,
    mode: str,
    provider: str,
    dry_run: bool,
    output_dir: Path = Path("outputs/llm_synthesis_runs"),
) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_type = "dry_run" if dry_run else "real"
    filename = (
        f"{fixture_id}_{artifact_id}_{mode}_{provider}_{run_type}_"
        f"{timestamp}.json"
    )
    return output_dir / filename


def build_default_validation_report_path(
    *,
    synthesis_output_path: Path,
    report_dir: Path = Path("outputs/reports"),
) -> Path:
    return report_dir / f"{synthesis_output_path.stem}_validation_report.md"


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
    parser.add_argument("--output-path")
    parser.add_argument(
        "--output-dir",
        default="outputs/llm_synthesis_runs",
    )
    parser.add_argument(
        "--validation-report-output-path",
    )
    parser.add_argument(
        "--validation-report-dir",
        default="outputs/reports",
    )
    parser.add_argument(
        "--no-validation-report",
        action="store_true",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
    )
    args = parser.parse_args()

    artifact = json.loads(Path(args.artifact_path).read_text())
    output_path = None
    validation_report_output_path = None

    if not args.no_save:
        output_path = (
            Path(args.output_path)
            if args.output_path
            else build_default_output_path(
                fixture_id=artifact["artifact_identity"]["fixture_id"],
                artifact_id=artifact["artifact_identity"]["artifact_id"],
                mode=args.mode,
                provider=args.provider,
                dry_run=args.dry_run,
                output_dir=Path(args.output_dir),
            )
        )

        if not args.no_validation_report:
            validation_report_output_path = (
                Path(args.validation_report_output_path)
                if args.validation_report_output_path
                else build_default_validation_report_path(
                    synthesis_output_path=output_path,
                    report_dir=Path(args.validation_report_dir),
                )
            )

    result = run_llm_synthesis_demo(
        artifact_path=Path(args.artifact_path),
        mode=args.mode,
        provider_name=args.provider,
        dry_run=args.dry_run,
        calls_remaining=args.calls_remaining,
        tokens_remaining=args.tokens_remaining,
        output_path=output_path,
        validation_report_output_path=validation_report_output_path,
    )

    print(json.dumps(result, indent=2))

    if output_path is not None:
        print(f"\nSaved synthesis output: {output_path}")

    if validation_report_output_path is not None:
        print(f"Saved validation report: {validation_report_output_path}")


if __name__ == "__main__":
    _main()
