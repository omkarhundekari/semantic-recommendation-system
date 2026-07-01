import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning.candidate_prompt import build_candidate_generation_payload
from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.generation_provider import CandidateGenerationProvider
from planning.live_llm_guard import require_live_openai_access
from planning.openai_generation_provider import (
    OpenAICandidateGenerationProvider,
)
from planning.shadow_runner import (
    build_generation_request,
    run_shadow_plan,
)
from planning.evidence_brief import build_evidence_brief
from planning.evidence_curation import curate_evidence
from project_idea_generator import generate_project_ideas
from source_router import retrieve_evidence


DEFAULT_OUTPUT_DIR = Path("outputs/shadow_comparisons")


def _query_slug(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    return slug[:60] or "shadow-comparison"


def _legacy_summary(ideas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "title": idea.get("project_title", ""),
            "evidence_title": idea.get("evidence_title", ""),
            "evidence_source_type": idea.get(
                "evidence_source_type",
                "",
            ),
            "detected_domain": idea.get("detected_domain", ""),
        }
        for idea in ideas
    ]


def build_shadow_comparison_artifact(
    evidence_payload: Dict[str, Any],
    user_goal: str,
    constraints: Dict[str, Any],
    fixture_response: Optional[Dict[str, Any]] = None,
    provider: Optional[CandidateGenerationProvider] = None,
    execution_mode: str = "fixture",
) -> Dict[str, Any]:
    inference = evidence_payload.get("inference", {})
    evidence_items = evidence_payload.get("merged_results", [])

    legacy_ideas = generate_project_ideas(
        search_results=evidence_items,
        user_query=user_goal,
        max_ideas=3,
        constraints=constraints,
        detected_domain=inference.get("inferred_focus"),
    )

    curation = curate_evidence(
        evidence_items=evidence_items,
        user_query=user_goal,
    )
    curated_items = [
        entry.item
        for entry in curation.retained
    ]

    brief = build_evidence_brief(
        evidence_items=curated_items,
        user_query=user_goal,
    )
    generation_request = build_generation_request(
        user_goal=user_goal,
        constraints=constraints,
    )

    v2_shadow: Dict[str, Any] = {
        "status": "prompt_ready",
        "evidence_curation": curation.to_dict(),
        "evidence_brief": brief.to_dict(),
        "candidate_generation_payload": (
            build_candidate_generation_payload(
                brief=brief,
                request=generation_request,
            )
        ),
        "selected_candidates": [],
        "diagnostics": {
            "provider_called": False,
            "message": (
                "No provider fixture was supplied. The artifact contains "
                "the exact evidence-grounded payload that a real provider "
                "must answer."
            ),
        },
    }

    if fixture_response is not None and provider is None:
        provider = MockCandidateGenerationProvider(
            response=fixture_response
        )

    if provider is not None:
        report = run_shadow_plan(
            evidence_items=evidence_items,
            user_goal=user_goal,
            constraints=constraints,
            provider=provider,
            legacy_ideas=legacy_ideas,
            max_candidates=3,
        )

        v2_shadow = {
            "status": f"{execution_mode}_evaluated",
            "report": report.to_dict(),
            "selected_candidates": report.selected_candidates,
            "diagnostics": report.planning_diagnostics,
        }

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "query": user_goal,
        "constraints": constraints,
        "retrieval": {
            "selected_route": evidence_payload.get("selected_route"),
            "expanded_query": evidence_payload.get("expanded_query"),
            "focused_query": evidence_payload.get("focused_query"),
            "inference": inference,
            "merged_evidence_count": len(evidence_items),
        },
        "legacy_planner": {
            "direction_count": len(legacy_ideas),
            "directions": _legacy_summary(legacy_ideas),
        },
        "v2_shadow": v2_shadow,
    }


def write_shadow_comparison_artifact(
    artifact: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"{_query_slug(artifact['query'])}_"
        f"{artifact['generated_at_utc']}.json"
    )
    output_path.write_text(json.dumps(artifact, indent=2))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare legacy planning with the V2 shadow-planning path."
        )
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language project goal.",
    )
    parser.add_argument(
        "--selected-direction",
        default=None,
        help="Optional confirmed planning direction.",
    )
    parser.add_argument(
        "--skill-level",
        default="",
    )
    parser.add_argument(
        "--time-available",
        default="",
    )
    parser.add_argument(
        "--target-role",
        action="append",
        default=[],
        help="Repeat for multiple roles.",
    )
    parser.add_argument(
        "--preferred-stack",
        action="append",
        default=[],
        help="Repeat for multiple technologies.",
    )
    parser.add_argument(
        "--fixture-response",
        default=None,
        help=(
            "Optional JSON provider-response fixture. When omitted, "
            "the artifact contains a V2 prompt-ready payload only."
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "openai"],
        default="mock",
        help="Provider used only for an explicit local evaluation.",
    )
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
        help="Required together with .env settings for a paid OpenAI run.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.provider == "openai":
        require_live_openai_access(
            provider_name=args.provider,
            allow_live_llm=args.allow_live_llm,
        )

    constraints = {
        "skill_level": args.skill_level,
        "time_available": args.time_available,
        "target_roles": args.target_role,
        "preferred_stack": args.preferred_stack,
    }

    evidence_payload = retrieve_evidence(
        user_query=args.query,
        top_k=6,
        selected_direction=args.selected_direction,
    )

    fixture_response = None

    if args.fixture_response:
        fixture_path = Path(args.fixture_response)

        if not fixture_path.exists():
            raise SystemExit(
                f"Fixture response was not found: {fixture_path}"
            )

        fixture_response = json.loads(fixture_path.read_text())

    provider = None
    execution_mode = "fixture"

    if args.provider == "openai":
        if fixture_response is not None:
            raise SystemExit(
                "Use either --fixture-response or --provider openai, not both."
            )

        provider = OpenAICandidateGenerationProvider()
        execution_mode = "live"

    artifact = build_shadow_comparison_artifact(
        evidence_payload=evidence_payload,
        user_goal=args.query,
        constraints=constraints,
        fixture_response=fixture_response,
        provider=provider,
        execution_mode=execution_mode,
    )

    output_path = write_shadow_comparison_artifact(
        artifact=artifact,
        output_dir=Path(args.output_dir),
    )

    print(f"Wrote shadow comparison artifact: {output_path}")
    print(
        "Legacy directions:",
        artifact["legacy_planner"]["direction_count"],
    )
    print(
        "V2 status:",
        artifact["v2_shadow"]["status"],
    )


if __name__ == "__main__":
    main()
