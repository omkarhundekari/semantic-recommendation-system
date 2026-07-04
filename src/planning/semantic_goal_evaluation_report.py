from typing import Any, Dict, List, Optional, Sequence

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.semantic_escalation import (
    build_low_margin_escalation_details,
)
from planning.semantic_goal_evaluation import (
    evaluate_labeled_ranking,
    evaluate_labeled_rankings,
)


def _build_request(case: Dict[str, Any]) -> CandidateGenerationRequest:
    return CandidateGenerationRequest(
        user_goal=str(case["user_goal"]),
        skill_level=str(case.get("skill_level", "")),
        time_available=str(case.get("time_available", "")),
        target_roles=list(case.get("target_roles", [])),
        preferred_stack=list(case.get("preferred_stack", [])),
    )


def _build_candidates(
    candidate_entries: Sequence[Dict[str, Any]],
) -> List[CandidateDirection]:
    return [
        CandidateDirection(
            title=str(entry["title"]),
            problem_statement=str(entry["problem_statement"]),
            target_user=str(entry["target_user"]),
            core_workflow=list(entry.get("core_workflow", [])),
            mvp_scope=list(entry.get("mvp_scope", [])),
            success_metrics=list(entry.get("success_metrics", [])),
            evidence_relationship=str(
                entry.get("evidence_relationship", "")
            ),
            source_ids=list(entry.get("source_ids", [])),
            assumptions=list(entry.get("assumptions", [])),
            suggested_stack=list(entry.get("suggested_stack", [])),
        )
        for entry in candidate_entries
    ]


def build_semantic_goal_evaluation_report(
    dataset: Dict[str, Any],
    embedding_scorer: Any,
    cross_encoder_scorer: Optional[Any] = None,
    top_k: int = 3,
    margin_threshold: float = 0.05,
) -> Dict[str, Any]:
    """
    Build an evaluation-only report for semantic scoring and ambiguity routing.

    Dataset labels are used only for offline measurement. They never affect
    production candidate selection, embedding scoring, or cross-encoder routing.
    """
    case_reports: Dict[str, Dict[str, Any]] = {}
    embedding_rankings: Dict[str, List[Dict[str, Any]]] = {}
    cross_encoder_rankings: Dict[str, List[Dict[str, Any]]] = {}

    for case in dataset.get("cases", []):
        case_id = str(case["id"])
        candidate_entries = list(case.get("candidates", []))
        request = _build_request(case)
        candidates = _build_candidates(candidate_entries)

        embedding_results = embedding_scorer.score_candidates(
            request,
            candidates,
        )

        escalation_details = build_low_margin_escalation_details(
            results=embedding_results,
            top_k=top_k,
            margin_threshold=margin_threshold,
        )

        embedding_scored_candidates: List[Dict[str, Any]] = []
        escalated_pairs = []

        for entry, candidate, result in zip(
            candidate_entries,
            candidates,
            embedding_results,
        ):
            detail = escalation_details[result.candidate_key]

            embedding_scored_candidates.append(
                {
                    "candidate_id": str(entry["id"]),
                    "label": int(entry["label"]),
                    "raw_cosine": result.trace.raw_cosine,
                    "normalized_score": result.trace.normalized_score,
                    "candidate_key": result.candidate_key,
                    "embedding_rank": detail["embedding_rank"],
                    "top_embedding_margin": (
                        detail["top_embedding_margin"]
                    ),
                    "escalated": detail["escalated"],
                }
            )

            if detail["escalated"]:
                escalated_pairs.append((entry, candidate, result))

        embedding_rankings[case_id] = embedding_scored_candidates

        cross_encoder_report = None
        cross_encoder_scored_candidates: List[Dict[str, Any]] = []

        if cross_encoder_scorer is not None and escalated_pairs:
            cross_encoder_results = (
                cross_encoder_scorer.score_candidates(
                    request,
                    [
                        candidate
                        for _, candidate, _ in escalated_pairs
                    ],
                )
            )

            for (entry, _, embedding_result), cross_result in zip(
                escalated_pairs,
                cross_encoder_results,
            ):
                cross_encoder_scored_candidates.append(
                    {
                        "candidate_id": str(entry["id"]),
                        "label": int(entry["label"]),
                        "cross_encoder_score": cross_result.raw_score,
                        "candidate_key": embedding_result.candidate_key,
                    }
                )

            cross_encoder_report = evaluate_labeled_ranking(
                cross_encoder_scored_candidates,
                score_field="cross_encoder_score",
            )
            cross_encoder_rankings[case_id] = (
                cross_encoder_scored_candidates
            )

        case_reports[case_id] = {
            "embedding": evaluate_labeled_ranking(
                embedding_scored_candidates,
                score_field="raw_cosine",
            ),
            "candidates": embedding_scored_candidates,
            "escalated_candidate_ids": [
                str(entry["id"])
                for entry, _, _ in escalated_pairs
            ],
            "cross_encoder": cross_encoder_report,
            "cross_encoder_candidates": (
                cross_encoder_scored_candidates
            ),
        }

    embedding_evaluation = evaluate_labeled_rankings(
        embedding_rankings,
        score_field="raw_cosine",
    )

    cross_encoder_evaluation = (
        evaluate_labeled_rankings(
            cross_encoder_rankings,
            score_field="cross_encoder_score",
        )
        if cross_encoder_rankings
        else None
    )

    return {
        "schema_version": "1.0",
        "routing_policy": {
            "top_k": top_k,
            "margin_threshold": margin_threshold,
        },
        "case_reports": case_reports,
        "summary": {
            "evaluated_case_count": len(case_reports),
            "escalated_case_count": sum(
                1
                for report in case_reports.values()
                if report["escalated_candidate_ids"]
            ),
            "embedding_evaluation": embedding_evaluation,
            "cross_encoder_evaluation": cross_encoder_evaluation,
        },
    }

import json
from datetime import datetime, timezone
from pathlib import Path


def write_semantic_goal_evaluation_report(
    report: Dict[str, Any],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / (
        f"semantic_goal_evaluation_{timestamp}.json"
    )
    output_path.write_text(json.dumps(report, indent=2))
    return output_path


def format_semantic_goal_evaluation_summary(
    report: Dict[str, Any],
) -> str:
    routing_policy = report["routing_policy"]
    summary = report["summary"]

    lines = [
        "Semantic goal evaluation report",
        (
            "routing: "
            f"top_k={routing_policy['top_k']} | "
            f"margin_threshold={routing_policy['margin_threshold']}"
        ),
        (
            "summary: "
            f"cases={summary['evaluated_case_count']} | "
            f"escalated_cases={summary['escalated_case_count']} | "
            "embedding_accuracy="
            f"{summary['embedding_evaluation']['overall_pairwise_accuracy']:.4f}"
        ),
    ]

    cross_encoder_evaluation = summary.get(
        "cross_encoder_evaluation"
    )
    if cross_encoder_evaluation is not None:
        lines.append(
            "cross_encoder_accuracy="
            f"{cross_encoder_evaluation['overall_pairwise_accuracy']:.4f}"
        )

    for case_id, case_report in report["case_reports"].items():
        embedding = case_report["embedding"]
        escalated_ids = case_report["escalated_candidate_ids"]

        lines.append("")
        lines.append(case_id)
        lines.append(
            "  embedding: "
            f"top={embedding['top_candidate_id']} "
            f"(label={embedding['top_candidate_label']}) | "
            "accuracy="
            f"{embedding['pairwise_accuracy']:.4f}"
        )
        lines.append(
            "  escalated="
            + (
                ", ".join(escalated_ids)
                if escalated_ids
                else "none"
            )
        )

        cross_encoder = case_report.get("cross_encoder")
        if cross_encoder is not None:
            lines.append(
                "  cross_encoder: "
                f"top={cross_encoder['top_candidate_id']} "
                f"(label={cross_encoder['top_candidate_label']}) | "
                "accuracy="
                f"{cross_encoder['pairwise_accuracy']:.4f}"
            )

    return "\n".join(lines)

import argparse


DEFAULT_DATASET_PATH = Path("data/semantic_goal_eval_v1.json")
DEFAULT_OUTPUT_DIR = Path("outputs/semantic_goal_evaluations")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate semantic goal relevance and ambiguity-based "
            "cross-encoder routing on the labeled benchmark."
        )
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Path to the labeled semantic-goal evaluation dataset.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for the local JSON report artifact.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Maximum embedding-ranked candidates eligible for escalation.",
    )
    parser.add_argument(
        "--margin-threshold",
        type=float,
        default=0.05,
        help="Experimental embedding-margin threshold for escalation.",
    )
    parser.add_argument(
        "--embedding-only",
        action="store_true",
        help="Skip cross-encoder scoring and report embedding results only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        raise SystemExit(
            f"Evaluation dataset was not found: {dataset_path}"
        )

    dataset = json.loads(dataset_path.read_text())

    from planning.cross_encoder_goal_adapter import (
        CrossEncoderGoalPairScorer,
    )
    from planning.cross_encoder_goal_relevance import (
        CrossEncoderGoalRelevanceScorer,
    )
    from planning.semantic_goal_adapter import (
        SemanticEngineTextEncoder,
    )
    from planning.semantic_goal_relevance import (
        GoalRelevanceScorer,
    )
    from reranker import CrossEncoderReranker
    from semantic_engine import SemanticEngine

    embedding_scorer = GoalRelevanceScorer(
        SemanticEngineTextEncoder(SemanticEngine())
    )

    cross_encoder_scorer = None
    if not args.embedding_only:
        cross_encoder_scorer = CrossEncoderGoalRelevanceScorer(
            CrossEncoderGoalPairScorer(
                CrossEncoderReranker()
            )
        )

    report = build_semantic_goal_evaluation_report(
        dataset=dataset,
        embedding_scorer=embedding_scorer,
        cross_encoder_scorer=cross_encoder_scorer,
        top_k=args.top_k,
        margin_threshold=args.margin_threshold,
    )

    output_path = write_semantic_goal_evaluation_report(
        report=report,
        output_dir=Path(args.output_dir),
    )

    print(format_semantic_goal_evaluation_summary(report))
    print(f"\nWrote evaluation artifact: {output_path}")


if __name__ == "__main__":
    main()
