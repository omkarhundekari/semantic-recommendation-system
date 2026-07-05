import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _latest_matching_artifact(
    output_dir: Path,
    user_goal: str,
) -> Optional[Dict[str, Any]]:
    matches = []

    for path in output_dir.glob("*.json"):
        try:
            artifact = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue

        if artifact.get("query") == user_goal:
            matches.append((path, artifact))

    if not matches:
        return None

    return max(
        matches,
        key=lambda item: item[0].stat().st_mtime,
    )[1]


def _case_report(
    case: Dict[str, Any],
    artifact: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if artifact is None:
        return {
            "status": "missing_artifact",
            "manual_review": case["manual_review"],
        }

    shadow = artifact.get("v2_shadow", {})
    diagnostics = shadow.get("diagnostics", {})
    readiness = shadow.get("shadow_readiness", {})
    diversity = shadow.get("semantic_candidate_diversity")
    goal_relevance = shadow.get("semantic_goal_relevance", [])
    grounding = shadow.get("grounding_adequacy", [])

    goal_scores = [
        trace.get("raw_cosine")
        for trace in goal_relevance
        if trace.get("raw_cosine") is not None
    ]
    grounding_scores = [
        trace.get("min_cited_alignment")
        for trace in grounding
        if trace.get("min_cited_alignment") is not None
    ]

    return {
        "status": "evaluated",
        "artifact_generated_at_utc": artifact.get("generated_at_utc"),
        "generation_metadata": shadow.get("generation_metadata", {}),
        "planning_diagnostics": diagnostics,
        "shadow_readiness": readiness,
        "semantic_candidate_diversity": diversity,
        "goal_relevance_summary": {
            "candidate_count": len(goal_scores),
            "minimum_raw_cosine": (
                round(min(goal_scores), 4)
                if goal_scores
                else None
            ),
            "maximum_raw_cosine": (
                round(max(goal_scores), 4)
                if goal_scores
                else None
            ),
        },
        "grounding_summary": {
            "candidate_count": len(grounding),
            "adequacy_classes": [
                trace.get("adequacy_class")
                for trace in grounding
            ],
            "minimum_cited_alignment": (
                round(min(grounding_scores), 4)
                if grounding_scores
                else None
            ),
        },
        "manual_review": case["manual_review"],
    }


def build_openai_planner_evaluation_report(
    dataset: Dict[str, Any],
    output_dir: Path,
) -> Dict[str, Any]:
    case_reports = {}

    for case in dataset.get("cases", []):
        artifact = _latest_matching_artifact(
            output_dir=output_dir,
            user_goal=case["user_goal"],
        )
        case_reports[case["id"]] = _case_report(case, artifact)

    evaluated_reports = [
        report
        for report in case_reports.values()
        if report["status"] == "evaluated"
    ]

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "case_reports": case_reports,
        "summary": {
            "configured_case_count": len(case_reports),
            "evaluated_case_count": len(evaluated_reports),
            "missing_artifact_case_count": (
                len(case_reports) - len(evaluated_reports)
            ),
            "ready_case_count": sum(
                1
                for report in evaluated_reports
                if report["shadow_readiness"].get("status") == "ready"
            ),
            "diversity_pass_case_count": sum(
                1
                for report in evaluated_reports
                if report["semantic_candidate_diversity"]
                and report["semantic_candidate_diversity"].get("passed")
            ),
        },
    }


def write_openai_planner_evaluation_report(
    report: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        "openai_planner_evaluation_"
        f"{report['generated_at_utc']}.json"
    )
    output_path.write_text(json.dumps(report, indent=2))
    return output_path


DEFAULT_DATASET_PATH = Path("data/openai_planner_eval_v1.json")
DEFAULT_ARTIFACT_DIR = Path("outputs/shadow_comparisons")
DEFAULT_OUTPUT_DIR = Path("outputs/openai_planner_evaluations")


def format_openai_planner_evaluation_summary(
    report: Dict[str, Any],
) -> str:
    summary = report["summary"]

    return "\n".join(
        [
            "OpenAI planner evaluation report",
            (
                "cases: "
                f"{summary['evaluated_case_count']}/"
                f"{summary['configured_case_count']} evaluated"
            ),
            (
                "missing artifacts: "
                f"{summary['missing_artifact_case_count']}"
            ),
            f"ready cases: {summary['ready_case_count']}",
            (
                "semantic diversity passes: "
                f"{summary['diversity_pass_case_count']}"
            ),
        ]
    )


def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Summarize local OpenAI shadow-planning artifacts against "
            "the planner evaluation manifest."
        )
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Committed planner evaluation manifest.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=str(DEFAULT_ARTIFACT_DIR),
        help="Directory containing local shadow comparison artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for the local evaluation report artifact.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_path = Path(args.dataset)

    if not dataset_path.exists():
        raise SystemExit(
            f"Evaluation manifest was not found: {dataset_path}"
        )

    dataset = json.loads(dataset_path.read_text())

    report = build_openai_planner_evaluation_report(
        dataset=dataset,
        output_dir=Path(args.artifact_dir),
    )

    output_path = write_openai_planner_evaluation_report(
        report=report,
        output_dir=Path(args.output_dir),
    )

    print(format_openai_planner_evaluation_summary(report))
    print(f"\nWrote evaluation artifact: {output_path}")


if __name__ == "__main__":
    main()
