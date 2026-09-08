import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.live_llm_guard import require_live_openai_access
from planning.openai_generation_provider import (
    OpenAICandidateGenerationProvider,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_adapter import SemanticEngineTextEncoder
from planning.successor_planner import build_successor_plan
from query_understanding import understand_query
from semantic_engine import SemanticEngine
from source_router import retrieve_evidence


DEFAULT_DATASET_PATH = Path("data/openai_planner_eval_v1.json")
DEFAULT_OUTPUT_DIR = Path("outputs/successor_measurements")


def _constraints(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "skill_level": case["skill_level"],
        "time_available": case["time_available"],
        "target_roles": list(case["target_roles"]),
        "preferred_stack": list(case["preferred_stack"]),
    }


def _usage(provider: Any) -> Dict[str, Optional[int]]:
    usage = getattr(provider, "last_usage", {}) or {}

    return {
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }


def measure_successor_case(
    case: Dict[str, Any],
    provider: Any,
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
    retrieve: Callable[..., Dict[str, Any]] = retrieve_evidence,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    constraints = _constraints(case)
    understanding = understand_query(
        goal=case["user_goal"],
        constraints=constraints,
    )

    started = clock()
    evidence_payload = retrieve(
        user_query=case["user_goal"],
        top_k=6,
        intent_hints=understanding["direction_hints"],
        selected_direction=None,
    )

    inference = evidence_payload.get("inference", {})
    detected_domain = inference.get("inferred_focus") or None
    evidence_items = evidence_payload.get("merged_results", [])

    result = build_successor_plan(
        evidence_items=evidence_items,
        user_goal=case["user_goal"],
        constraints=constraints,
        detected_domain=detected_domain,
        provider=provider,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )
    elapsed_seconds = round(clock() - started, 4)

    return {
        "case_id": case["id"],
        "user_goal": case["user_goal"],
        "status": result.status,
        "reason_code": result.diagnostics.get(
            "reason_code",
            result.status,
        ),
        "elapsed_seconds": elapsed_seconds,
        "detected_domain": detected_domain,
        "retrieval": {
            "merged_result_count": len(evidence_items),
        },
        "generation": {
            "model": getattr(provider, "model", None),
            "usage": _usage(provider),
        },
        "diagnostics": result.diagnostics,
        "assessment": result.assessment,
        "candidates": [
            candidate.to_dict()
            for candidate in result.candidates
        ] if result.ready else [],
    }


def build_successor_measurement_report(
    dataset: Dict[str, Any],
    provider_factory: Callable[[], Any],
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
    retrieve: Callable[..., Dict[str, Any]] = retrieve_evidence,
    clock: Callable[[], float] = time.perf_counter,
) -> Dict[str, Any]:
    cases = [
        measure_successor_case(
            case=case,
            provider=provider_factory(),
            evidence_support_scorer=evidence_support_scorer,
            semantic_diversity_scorer=semantic_diversity_scorer,
            retrieve=retrieve,
            clock=clock,
        )
        for case in dataset.get("cases", [])
    ]

    status_counts = Counter(case["status"] for case in cases)
    reason_counts = Counter(case["reason_code"] for case in cases)
    elapsed = [case["elapsed_seconds"] for case in cases]

    usage_records = [
        case["generation"]["usage"]
        for case in cases
    ]

    ready_count = status_counts.get("ready", 0)
    case_count = len(cases)

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "cases": cases,
        "summary": {
            "case_count": case_count,
            "ready_count": ready_count,
            "ready_rate": (
                round(ready_count / case_count, 4)
                if case_count
                else None
            ),
            "status_counts": dict(sorted(status_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "needs_repair_count": status_counts.get(
                "needs_repair",
                0,
            ),
            "average_elapsed_seconds": (
                round(sum(elapsed) / len(elapsed), 4)
                if elapsed
                else None
            ),
            "maximum_elapsed_seconds": (
                round(max(elapsed), 4)
                if elapsed
                else None
            ),
            "total_input_tokens": sum(
                int(record.get("input_tokens") or 0)
                for record in usage_records
            ),
            "total_output_tokens": sum(
                int(record.get("output_tokens") or 0)
                for record in usage_records
            ),
            "total_tokens": sum(
                int(record.get("total_tokens") or 0)
                for record in usage_records
            ),
        },
    }


def write_successor_measurement_report(
    report: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / (
        "successor_measurement_"
        f"{report['generated_at_utc']}.json"
    )
    path.write_text(json.dumps(report, indent=2))
    return path


def format_successor_measurement_summary(
    report: Dict[str, Any],
) -> str:
    summary = report["summary"]

    return "\n".join(
        [
            "Successor planner measurement",
            (
                "ready: "
                f"{summary['ready_count']}/"
                f"{summary['case_count']}"
            ),
            f"ready rate: {summary['ready_rate']}",
            (
                "needs repair: "
                f"{summary['needs_repair_count']}"
            ),
            (
                "average elapsed seconds: "
                f"{summary['average_elapsed_seconds']}"
            ),
            f"total tokens: {summary['total_tokens']}",
            f"status counts: {summary['status_counts']}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the fail-closed successor planner against the "
            "committed planner evaluation manifest."
        )
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--allow-live-llm",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    require_live_openai_access(
        provider_name="openai",
        allow_live_llm=args.allow_live_llm,
    )

    dataset_path = Path(args.dataset)

    if not dataset_path.exists():
        raise SystemExit(
            f"Evaluation manifest was not found: {dataset_path}"
        )

    dataset = json.loads(dataset_path.read_text())

    semantic_encoder = SemanticEngineTextEncoder(
        SemanticEngine()
    )
    evidence_support_scorer = CandidateEvidenceSupportScorer(
        semantic_encoder
    )
    semantic_diversity_scorer = SemanticCandidateDiversityScorer(
        semantic_encoder
    )

    report = build_successor_measurement_report(
        dataset=dataset,
        provider_factory=OpenAICandidateGenerationProvider,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )

    output_path = write_successor_measurement_report(
        report,
        Path(args.output_dir),
    )

    print(format_successor_measurement_summary(report))
    print(f"\nWrote measurement artifact: {output_path}")


if __name__ == "__main__":
    main()
