from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from planning.llm_routing_policy import DEEP_MODE, FAST_MODE, INTERVIEW_MODE
from planning.llm_synthesis_demo import (
    build_default_output_path,
    build_default_validation_report_path,
    run_llm_synthesis_demo,
)


@dataclass(frozen=True)
class BatchSynthesisEvaluationSummary:
    artifact_count: int
    routed_count: int
    blocked_count: int
    valid_count: int
    invalid_count: int
    invented_source_output_count: int
    grounded_direction_count: int
    ungrounded_direction_count: int
    output_paths: tuple[str, ...]
    validation_report_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def discover_artifact_paths(*, artifact_dir: Path) -> list[Path]:
    return sorted(artifact_dir.glob("*/*.json"))


def run_batch_synthesis_evaluation(
    *,
    artifact_paths: list[Path],
    mode: str = DEEP_MODE,
    provider_name: str = "fake",
    dry_run: bool = True,
    calls_remaining: int = 5,
    tokens_remaining: int = 10_000,
    output_dir: Path = Path("outputs/llm_synthesis_runs"),
    validation_report_dir: Path = Path("outputs/reports"),
    save_outputs: bool = True,
) -> dict[str, Any]:
    results = []

    for artifact_path in artifact_paths:
        artifact = json.loads(artifact_path.read_text())
        fixture_id = artifact["artifact_identity"]["fixture_id"]
        artifact_id = artifact["artifact_identity"]["artifact_id"]

        output_path = None
        validation_report_output_path = None

        if save_outputs:
            output_path = build_default_output_path(
                fixture_id=fixture_id,
                artifact_id=artifact_id,
                mode=mode,
                provider=provider_name,
                dry_run=dry_run,
                output_dir=output_dir,
            )
            validation_report_output_path = build_default_validation_report_path(
                synthesis_output_path=output_path,
                report_dir=validation_report_dir,
            )

        result = run_llm_synthesis_demo(
            artifact_path=artifact_path,
            mode=mode,
            provider_name=provider_name,
            dry_run=dry_run,
            calls_remaining=calls_remaining,
            tokens_remaining=tokens_remaining,
            output_path=output_path,
            validation_report_output_path=validation_report_output_path,
        )
        results.append(result)

    summary = summarize_batch_synthesis_results(results)

    return {
        "summary": summary.to_dict(),
        "results": results,
    }


def summarize_batch_synthesis_results(
    results: list[dict[str, Any]],
) -> BatchSynthesisEvaluationSummary:
    routed_count = 0
    blocked_count = 0
    valid_count = 0
    invalid_count = 0
    invented_source_output_count = 0
    grounded_direction_count = 0
    ungrounded_direction_count = 0
    output_paths = []
    validation_report_paths = []

    for result in results:
        routing_decision = result.get("routing_decision", {})
        if routing_decision.get("should_route"):
            routed_count += 1
        else:
            blocked_count += 1

        validation = result.get("saved_output_validation")
        if validation:
            if validation.get("is_valid"):
                valid_count += 1
            else:
                invalid_count += 1

            if validation.get("invented_source_ids"):
                invented_source_output_count += 1

            for trace in validation.get("direction_grounding_traces", []):
                if trace.get("is_grounded"):
                    grounded_direction_count += 1
                else:
                    ungrounded_direction_count += 1

            output_path = validation.get("output_path")
            if output_path:
                output_paths.append(output_path)

        validation_report_output_path = result.get("validation_report_output_path")
        if validation_report_output_path:
            validation_report_paths.append(validation_report_output_path)

    return BatchSynthesisEvaluationSummary(
        artifact_count=len(results),
        routed_count=routed_count,
        blocked_count=blocked_count,
        valid_count=valid_count,
        invalid_count=invalid_count,
        invented_source_output_count=invented_source_output_count,
        grounded_direction_count=grounded_direction_count,
        ungrounded_direction_count=ungrounded_direction_count,
        output_paths=tuple(output_paths),
        validation_report_paths=tuple(validation_report_paths),
    )


def write_batch_synthesis_summary(
    *,
    batch_result: dict[str, Any],
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(batch_result, indent=2))
    return output_path


def _artifact_paths_from_args(args: argparse.Namespace) -> list[Path]:
    if args.artifact_path:
        return [Path(path) for path in args.artifact_path]

    return discover_artifact_paths(
        artifact_dir=Path(args.artifact_dir),
    )


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-path", action="append")
    parser.add_argument(
        "--artifact-dir",
        default="data/manual_fixture_artifacts",
    )
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
    parser.add_argument(
        "--output-dir",
        default="outputs/llm_synthesis_runs",
    )
    parser.add_argument(
        "--validation-report-dir",
        default="outputs/reports",
    )
    parser.add_argument(
        "--summary-output-path",
        default="outputs/reports/llm_synthesis_batch_summary.json",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
    )
    args = parser.parse_args()

    batch_result = run_batch_synthesis_evaluation(
        artifact_paths=_artifact_paths_from_args(args),
        mode=args.mode,
        provider_name=args.provider,
        dry_run=args.dry_run,
        calls_remaining=args.calls_remaining,
        tokens_remaining=args.tokens_remaining,
        output_dir=Path(args.output_dir),
        validation_report_dir=Path(args.validation_report_dir),
        save_outputs=not args.no_save,
    )

    if not args.no_save:
        write_batch_synthesis_summary(
            batch_result=batch_result,
            output_path=Path(args.summary_output_path),
        )

    print(json.dumps(batch_result["summary"], indent=2))


if __name__ == "__main__":
    _main()
