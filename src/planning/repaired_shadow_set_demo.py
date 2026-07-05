import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from planning.candidate_regeneration_intake import (
    intake_regenerated_candidate,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
    load_regeneration_source_artifact,
)
from planning.repaired_shadow_set import (
    RepairedShadowSetEvaluation,
    evaluate_repaired_shadow_set,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_adapter import SemanticEngineTextEncoder
from semantic_engine import SemanticEngine


DEFAULT_OUTPUT_DIR = Path("outputs/repaired_shadow_sets")


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_accepted_replacement(
    regeneration_path: Path,
    source: RegenerationSourceArtifact,
):
    if not regeneration_path.exists():
        raise ValueError(
            f"Regeneration artifact was not found: {regeneration_path}"
        )

    try:
        artifact = json.loads(regeneration_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Regeneration artifact is not valid JSON."
        ) from exc

    cycle = artifact.get("cycle", {})

    if not isinstance(cycle, dict):
        raise ValueError("Regeneration artifact does not contain a cycle.")

    evaluation = cycle.get("replacement_evaluation", {})

    if not isinstance(evaluation, dict):
        raise ValueError(
            "Regeneration artifact lacks replacement evaluation."
        )

    if not evaluation.get("accepted_as_diverse_replacement", False):
        raise ValueError(
            "Regeneration artifact was not accepted as a diverse replacement."
        )

    intake = cycle.get("intake", {})

    if not isinstance(intake, dict):
        raise ValueError("Regeneration artifact lacks intake data.")

    candidate_payload = intake.get("candidate")

    if not isinstance(candidate_payload, dict):
        raise ValueError(
            "Regeneration artifact does not contain a candidate."
        )

    candidate_intake = intake_regenerated_candidate(
        payload={"candidate": candidate_payload},
        brief=source.brief,
    )

    if not candidate_intake.is_valid:
        raise ValueError(
            "Saved regeneration candidate no longer passes validation."
        )

    return candidate_intake.candidate


def build_repaired_shadow_set_artifact(
    source_path: Path,
    regeneration_path: Path,
    directive_index: int,
    result: RepairedShadowSetEvaluation,
) -> Dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_at_utc": _timestamp(),
        "execution_mode": "local_repaired_shadow_set",
        "source_shadow_artifact": str(source_path),
        "accepted_regeneration_artifact": str(regeneration_path),
        "directive_index": directive_index,
        "repaired_shadow_set": result.to_dict(),
    }


def write_repaired_shadow_set_artifact(
    artifact: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"repaired_shadow_set_{artifact['generated_at_utc']}.json"
    )
    output_path.write_text(json.dumps(artifact, indent=2))
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild and audit a repaired shadow candidate set without "
            "calling an LLM."
        )
    )
    parser.add_argument(
        "--source-artifact",
        required=True,
        help="Shadow comparison artifact containing the repair directive.",
    )
    parser.add_argument(
        "--regeneration-artifact",
        required=True,
        help="Accepted regeneration-cycle artifact.",
    )
    parser.add_argument(
        "--directive-index",
        type=int,
        default=0,
        help="Repair directive index from the source artifact.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_path = Path(args.source_artifact)
    regeneration_path = Path(args.regeneration_artifact)

    source = load_regeneration_source_artifact(
        path=source_path,
        directive_index=args.directive_index,
    )

    replacement = load_accepted_replacement(
        regeneration_path=regeneration_path,
        source=source,
    )

    encoder = SemanticEngineTextEncoder(SemanticEngine())

    result = evaluate_repaired_shadow_set(
        source=source,
        replacement=replacement,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    artifact = build_repaired_shadow_set_artifact(
        source_path=source_path,
        regeneration_path=regeneration_path,
        directive_index=args.directive_index,
        result=result,
    )

    output_path = write_repaired_shadow_set_artifact(
        artifact=artifact,
        output_dir=Path(args.output_dir),
    )

    print(f"Wrote repaired shadow-set artifact: {output_path}")
    print("Status:", result.status)
    print("Selected candidates:")

    for candidate in result.selected_candidates:
        print("-", candidate["title"])

    print(
        "Eligible candidates:",
        result.signals["eligible_candidate_count"],
    )
    print(
        "Semantic diversity passed:",
        result.signals["semantic_diversity_passed"],
    )


if __name__ == "__main__":
    main()
