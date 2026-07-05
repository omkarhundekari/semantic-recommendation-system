import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from planning.candidate_regeneration_cycle import (
    CandidateRegenerationCycle,
    run_mock_regeneration_cycle,
)
from planning.candidate_regeneration_prompt import (
    build_candidate_regeneration_prompt,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.live_llm_guard import require_live_openai_access
from planning.openai_generation_provider import (
    OpenAICandidateGenerationProvider,
)
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
    load_regeneration_source_artifact,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_adapter import SemanticEngineTextEncoder
from semantic_engine import SemanticEngine


DEFAULT_OUTPUT_DIR = Path("outputs/regeneration_cycles")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_regeneration_artifact(
    source: RegenerationSourceArtifact,
    cycle: CandidateRegenerationCycle,
    provider: Any,
) -> Dict[str, Any]:
    usage = getattr(provider, "last_usage", {})

    return {
        "schema_version": "1.0",
        "generated_at_utc": _timestamp(),
        "execution_mode": "guarded_live_regeneration",
        "source_artifact": str(source.path),
        "source_query": source.request.user_goal,
        "replacement_target": source.replaced_candidate.to_dict(),
        "retained_candidates": [
            candidate.to_dict()
            for candidate in source.retained_candidates
        ],
        "repair_directive": source.directive.to_dict(),
        "generation_metadata": {
            "provider_name": provider.__class__.__name__,
            "model": getattr(provider, "model", None),
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        },
        "cycle": cycle.to_dict(),
    }


def write_regeneration_artifact(
    artifact: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"regeneration_{artifact['generated_at_utc']}.json"
    )
    output_path.write_text(json.dumps(artifact, indent=2))
    return output_path


def run_guarded_regeneration(
    source: RegenerationSourceArtifact,
    provider: Any,
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
) -> CandidateRegenerationCycle:
    prompt = build_candidate_regeneration_prompt(
        brief=source.brief,
        request=source.request,
        directive=source.directive,
    )

    raw_response = provider.generate_regeneration(
        prompt,
        allow_live_llm=True,
    )

    return run_mock_regeneration_cycle(
        raw_response=raw_response,
        brief=source.brief,
        request=source.request,
        directive=source.directive,
        retained_candidates=source.retained_candidates,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run one guarded OpenAI regeneration from a shadow artifact."
        )
    )
    parser.add_argument(
        "--source-artifact",
        required=True,
        help="Path to a shadow comparison artifact with a repair directive.",
    )
    parser.add_argument(
        "--directive-index",
        type=int,
        default=0,
        help="Index of the repair directive to regenerate.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai"],
        required=True,
        help="Only OpenAI is supported for guarded regeneration.",
    )
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
        help="Required together with enabled OpenAI .env settings.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    require_live_openai_access(
        provider_name=args.provider,
        allow_live_llm=args.allow_live_llm,
    )

    source = load_regeneration_source_artifact(
        path=Path(args.source_artifact),
        directive_index=args.directive_index,
    )

    semantic_encoder = SemanticEngineTextEncoder(SemanticEngine())

    provider = OpenAICandidateGenerationProvider()

    cycle = run_guarded_regeneration(
        source=source,
        provider=provider,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            semantic_encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            semantic_encoder
        ),
    )

    artifact = build_regeneration_artifact(
        source=source,
        cycle=cycle,
        provider=provider,
    )

    output_path = write_regeneration_artifact(
        artifact=artifact,
        output_dir=Path(args.output_dir),
    )

    print(f"Wrote regeneration artifact: {output_path}")
    print(
        "Replacement status:",
        cycle.replacement_evaluation.replacement_status,
    )
    print("Accepted as diverse replacement:", cycle.accepted)


if __name__ == "__main__":
    main()
