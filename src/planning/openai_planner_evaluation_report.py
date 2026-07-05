import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.candidate_validator import validate_candidate
from planning.grounding_adequacy import (
    GroundingAdequacy,
    GroundingAdequacyTrace,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.promotion_eligibility import (
    assess_promotion_eligibility,
)
from planning.semantic_candidate_diversity import (
    CandidateDiversityPair,
    CandidateDiversityTrace,
)
from planning.semantic_diversification_repair import (
    build_semantic_diversification_repair_plan,
)
from planning.shadow_quality_warnings import (
    ShadowQualityWarning,
    ShadowQualityWarningAssessment,
    assess_shadow_quality_warnings,
)


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


def _quality_warning_assessment_from_dict(
    payload: Dict[str, Any],
) -> ShadowQualityWarningAssessment:
    return ShadowQualityWarningAssessment(
        warnings=[
            ShadowQualityWarning(
                code=str(item.get("code", "")),
                message=str(item.get("message", "")),
                details=dict(item.get("details", {})),
            )
            for item in payload.get("warnings", [])
            if isinstance(item, dict)
        ],
        signals=dict(payload.get("signals", {})),
    )


def _diversity_trace_from_dict(
    payload: Optional[Dict[str, Any]],
) -> Optional[CandidateDiversityTrace]:
    if not isinstance(payload, dict):
        return None

    return CandidateDiversityTrace(
        similarity_threshold=float(
            payload.get("similarity_threshold", 0.82)
        ),
        pairwise_similarity=[
            CandidateDiversityPair(
                candidate_a_title=str(
                    pair.get("candidate_a_title", "")
                ),
                candidate_b_title=str(
                    pair.get("candidate_b_title", "")
                ),
                raw_cosine=float(pair.get("raw_cosine", 0.0)),
                flagged=bool(pair.get("flagged", False)),
            )
            for pair in payload.get("pairwise_similarity", [])
            if isinstance(pair, dict)
        ],
        passed=bool(payload.get("passed", False)),
    )


def _grounding_by_title(
    grounding: List[Dict[str, Any]],
) -> Dict[str, GroundingAdequacyTrace]:
    result = {}

    for item in grounding:
        title = str(item.get("candidate_title", "")).strip()

        if not title:
            continue

        adequacy_value = str(
            item.get("adequacy_class", "")
        ).strip()

        try:
            adequacy_class = GroundingAdequacy(adequacy_value)
        except ValueError:
            continue

        result[title] = GroundingAdequacyTrace(
            candidate_title=title,
            adequacy_class=adequacy_class,
            cited_source_ids=list(item.get("cited_source_ids", [])),
            cited_source_scopes=list(
                item.get("cited_source_scopes", [])
            ),
            cited_alignment_scores=list(
                item.get("cited_alignment_scores", [])
            ),
            min_cited_alignment=item.get("min_cited_alignment"),
            max_cited_alignment=item.get("max_cited_alignment"),
            direct_sources_in_brief=int(
                item.get("direct_sources_in_brief", 0) or 0
            ),
            uncited_direct_sources=list(
                item.get("uncited_direct_sources", [])
            ),
            adequacy_reason=str(
                item.get("adequacy_reason", "")
            ),
        )

    return result


def _promotion_eligibility_from_artifact(
    shadow: Dict[str, Any],
    quality_warnings: Dict[str, Any],
) -> Dict[str, Any]:
    existing = shadow.get("promotion_eligibility")

    if isinstance(existing, dict):
        return existing

    selected_candidates = shadow.get("selected_candidates", [])
    grounding = shadow.get("grounding_adequacy", [])

    if not selected_candidates or not grounding:
        return {
            "status": "not_assessed",
            "candidate_assessments": [],
            "summary": {
                "eligible_count": 0,
                "needs_review_count": 0,
                "ineligible_count": 0,
            },
            "reason": (
                "The artifact lacks selected candidates or grounding "
                "traces required for promotion recomputation."
            ),
        }

    report = shadow.get("report", {})
    brief_payload = report.get("evidence_brief", {})

    sources = [
        EvidenceSource(
            source_id=str(source.get("source_id", "")),
            source_type=str(source.get("source_type", "unknown")),
            title=str(source.get("title", "")),
            excerpt=str(source.get("excerpt", "")),
            category=source.get("category"),
            url=source.get("url"),
            retrieval_rank=source.get("retrieval_rank"),
            retrieval_signals=dict(
                source.get("retrieval_signals", {})
            ),
            support_scope=str(
                source.get("support_scope", "direct")
            ),
            retention_reason=str(
                source.get("retention_reason", "")
            ),
        )
        for source in brief_payload.get("sources", [])
        if isinstance(source, dict)
    ]

    if not sources:
        return {
            "status": "not_assessed",
            "candidate_assessments": [],
            "summary": {
                "eligible_count": 0,
                "needs_review_count": 0,
                "ineligible_count": 0,
            },
            "reason": (
                "The artifact lacks an evidence brief required for "
                "promotion recomputation."
            ),
        }

    brief = EvidenceBrief(
        query=str(brief_payload.get("query", "")),
        sources=sources,
        source_counts=dict(brief_payload.get("source_counts", {})),
        recurring_concepts=list(
            brief_payload.get("recurring_concepts", [])
        ),
        coverage_warnings=list(
            brief_payload.get("coverage_warnings", [])
        ),
    )

    grounding_by_title = _grounding_by_title(grounding)
    warning_assessment = _quality_warning_assessment_from_dict(
        quality_warnings
    )
    diversity_trace = _diversity_trace_from_dict(
        shadow.get("semantic_candidate_diversity")
    )

    assessments = []

    for payload in selected_candidates:
        if not isinstance(payload, dict):
            continue

        try:
            candidate = CandidateDirection(
                **{
                    key: value
                    for key, value in payload.items()
                    if key != "ranking"
                }
            )
        except TypeError:
            continue

        candidate_grounding = grounding_by_title.get(candidate.title)

        if candidate_grounding is None:
            continue

        validation: CandidateValidationResult = validate_candidate(
            candidate,
            brief,
        )

        assessments.append(
            assess_promotion_eligibility(
                candidate=candidate,
                validation=validation,
                grounding=candidate_grounding,
                quality_warnings=warning_assessment,
                semantic_candidate_diversity=diversity_trace,
            ).to_dict()
        )

    if not assessments:
        return {
            "status": "not_assessed",
            "candidate_assessments": [],
            "summary": {
                "eligible_count": 0,
                "needs_review_count": 0,
                "ineligible_count": 0,
            },
            "reason": (
                "No selected candidate could be matched to a valid "
                "grounding trace."
            ),
        }

    return {
        "status": "recomputed",
        "candidate_assessments": assessments,
        "summary": {
            "eligible_count": sum(
                item["status"] == "eligible"
                for item in assessments
            ),
            "needs_review_count": sum(
                item["status"] == "needs_review"
                for item in assessments
            ),
            "ineligible_count": sum(
                item["status"] == "ineligible"
                for item in assessments
            ),
        },
    }


def _diversification_repair_from_artifact(
    shadow: Dict[str, Any],
) -> Dict[str, Any]:
    existing = shadow.get("semantic_diversification_repair")

    if isinstance(existing, dict):
        return existing

    selected_candidates = shadow.get("selected_candidates", [])
    diversity = shadow.get("semantic_candidate_diversity")

    if not selected_candidates or not isinstance(diversity, dict):
        return {
            "status": "not_assessed",
            "directives": [],
            "signals": {
                "candidate_count": 0,
                "close_cluster_count": 0,
                "replacement_count": 0,
            },
            "reason": (
                "The artifact lacks selected candidates or semantic "
                "diversity traces required for repair recomputation."
            ),
        }

    return build_semantic_diversification_repair_plan(
        selected_candidates=selected_candidates,
        semantic_candidate_diversity=diversity,
    ).to_dict()


def _candidate_promotion_audit(
    promotion_eligibility: Dict[str, Any],
    goal_relevance: List[Dict[str, Any]],
    grounding: List[Dict[str, Any]],
    diversity: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    goal_by_title = {
        str(trace.get("candidate_title", "")).strip(): trace
        for trace in goal_relevance
        if isinstance(trace, dict)
    }
    grounding_by_title = {
        str(trace.get("candidate_title", "")).strip(): trace
        for trace in grounding
        if isinstance(trace, dict)
    }

    nearest_pairs: Dict[str, Dict[str, Any]] = {}

    for pair in (
        diversity.get("pairwise_similarity", [])
        if isinstance(diversity, dict)
        else []
    ):
        if not isinstance(pair, dict):
            continue

        left = str(pair.get("candidate_a_title", "")).strip()
        right = str(pair.get("candidate_b_title", "")).strip()

        try:
            similarity = float(pair.get("raw_cosine"))
        except (TypeError, ValueError):
            continue

        for title, neighbor in ((left, right), (right, left)):
            current = nearest_pairs.get(title)

            if current is None or similarity > current["raw_cosine"]:
                nearest_pairs[title] = {
                    "candidate_title": neighbor,
                    "raw_cosine": round(similarity, 4),
                    "flagged": bool(pair.get("flagged", False)),
                }

    audit_rows = []

    for assessment in promotion_eligibility.get(
        "candidate_assessments",
        [],
    ):
        if not isinstance(assessment, dict):
            continue

        title = str(assessment.get("candidate_title", "")).strip()
        goal = goal_by_title.get(title, {})
        grounding_trace = grounding_by_title.get(title, {})

        audit_rows.append(
            {
                "candidate_title": title,
                "promotion_status": assessment.get("status"),
                "eligible_for_product_promotion": assessment.get(
                    "eligible_for_product_promotion",
                    False,
                ),
                "blocking_reasons": list(
                    assessment.get("blocking_reasons", [])
                ),
                "review_reasons": list(
                    assessment.get("review_reasons", [])
                ),
                "quality_warning_codes": list(
                    assessment.get("signals", {}).get(
                        "candidate_warning_codes",
                        [],
                    )
                ),
                "goal_relevance_raw_cosine": goal.get("raw_cosine"),
                "grounding_adequacy_class": grounding_trace.get(
                    "adequacy_class"
                ),
                "minimum_cited_alignment": grounding_trace.get(
                    "min_cited_alignment"
                ),
                "nearest_candidate_pair": nearest_pairs.get(title),
            }
        )

    return audit_rows


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
    coverage_warnings = readiness.get("signals", {}).get(
        "coverage_warnings",
        [],
    )

    quality_warnings = shadow.get("quality_warnings")

    if not isinstance(quality_warnings, dict):
        quality_warnings = assess_shadow_quality_warnings(
            coverage_warnings=coverage_warnings,
            semantic_goal_relevance=goal_relevance,
            grounding_adequacy=grounding,
            semantic_candidate_diversity=diversity,
        ).to_dict()

    promotion_eligibility = _promotion_eligibility_from_artifact(
        shadow=shadow,
        quality_warnings=quality_warnings,
    )
    diversification_repair = _diversification_repair_from_artifact(
        shadow=shadow,
    )

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
    diversity_pairs = (
        diversity.get("pairwise_similarity", [])
        if diversity
        else []
    )
    diversity_scores = [
        pair.get("raw_cosine")
        for pair in diversity_pairs
        if pair.get("raw_cosine") is not None
    ]

    return {
        "status": "evaluated",
        "artifact_generated_at_utc": artifact.get("generated_at_utc"),
        "generation_metadata": shadow.get("generation_metadata", {}),
        "planning_diagnostics": diagnostics,
        "shadow_readiness": readiness,
        "semantic_candidate_diversity": diversity,
        "quality_warnings": quality_warnings,
        "promotion_eligibility": promotion_eligibility,
        "semantic_diversification_repair": diversification_repair,
        "promotion_audit": _candidate_promotion_audit(
            promotion_eligibility=promotion_eligibility,
            goal_relevance=goal_relevance,
            grounding=grounding,
            diversity=diversity,
        ),
        "goal_relevance_summary": {
            "candidate_count": len(goal_scores),
            "minimum_raw_cosine": (
                round(min(goal_scores), 4)
                if goal_scores
                else None
            ),
            "average_raw_cosine": (
                round(sum(goal_scores) / len(goal_scores), 4)
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
            "average_cited_alignment": (
                round(
                    sum(grounding_scores) / len(grounding_scores),
                    4,
                )
                if grounding_scores
                else None
            ),
        },
        "diversity_summary": {
            "pair_count": len(diversity_scores),
            "highest_pair_similarity": (
                round(max(diversity_scores), 4)
                if diversity_scores
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

    goal_averages = [
        report["goal_relevance_summary"]["average_raw_cosine"]
        for report in evaluated_reports
        if report["goal_relevance_summary"]["average_raw_cosine"] is not None
    ]
    goal_minimums = [
        report["goal_relevance_summary"]["minimum_raw_cosine"]
        for report in evaluated_reports
        if report["goal_relevance_summary"]["minimum_raw_cosine"] is not None
    ]
    grounding_averages = [
        report["grounding_summary"]["average_cited_alignment"]
        for report in evaluated_reports
        if report["grounding_summary"]["average_cited_alignment"] is not None
    ]
    grounding_minimums = [
        report["grounding_summary"]["minimum_cited_alignment"]
        for report in evaluated_reports
        if report["grounding_summary"]["minimum_cited_alignment"] is not None
    ]
    highest_pair_similarities = [
        report["diversity_summary"]["highest_pair_similarity"]
        for report in evaluated_reports
        if report["diversity_summary"]["highest_pair_similarity"] is not None
    ]
    usage_records = [
        report["generation_metadata"].get("usage", {})
        for report in evaluated_reports
    ]

    quality_warning_counts = {}
    quality_warning_case_count = 0
    promotion_status_counts = {
        "eligible_count": 0,
        "needs_review_count": 0,
        "ineligible_count": 0,
        "not_assessed_case_count": 0,
    }
    diversification_repair_counts = {
        "repair_planned_case_count": 0,
        "no_repair_needed_case_count": 0,
        "not_assessed_case_count": 0,
        "close_cluster_count": 0,
        "planned_replacement_count": 0,
    }

    for report in evaluated_reports:
        warnings = report.get("quality_warnings", {}).get(
            "warnings",
            [],
        )

        if warnings:
            quality_warning_case_count += 1

        for warning in warnings:
            code = str(warning.get("code", "")).strip()

            if code:
                quality_warning_counts[code] = (
                    quality_warning_counts.get(code, 0) + 1
                )

        promotion = report.get("promotion_eligibility", {})
        promotion_summary = promotion.get("summary", {})

        if promotion.get("status") == "not_assessed":
            promotion_status_counts["not_assessed_case_count"] += 1
        else:
            for key in (
                "eligible_count",
                "needs_review_count",
                "ineligible_count",
            ):
                promotion_status_counts[key] += int(
                    promotion_summary.get(key, 0) or 0
                )

        repair = report.get("semantic_diversification_repair", {})
        repair_signals = repair.get("signals", {})

        if repair.get("status") == "repair_planned":
            diversification_repair_counts[
                "repair_planned_case_count"
            ] += 1
        elif repair.get("status") == "no_repair_needed":
            diversification_repair_counts[
                "no_repair_needed_case_count"
            ] += 1
        else:
            diversification_repair_counts[
                "not_assessed_case_count"
            ] += 1

        diversification_repair_counts["close_cluster_count"] += int(
            repair_signals.get("close_cluster_count", 0) or 0
        )
        diversification_repair_counts[
            "planned_replacement_count"
        ] += int(
            repair_signals.get("replacement_count", 0) or 0
        )

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
            "average_case_goal_relevance": (
                round(sum(goal_averages) / len(goal_averages), 4)
                if goal_averages
                else None
            ),
            "minimum_candidate_goal_relevance": (
                round(min(goal_minimums), 4)
                if goal_minimums
                else None
            ),
            "average_case_grounding_alignment": (
                round(
                    sum(grounding_averages) / len(grounding_averages),
                    4,
                )
                if grounding_averages
                else None
            ),
            "minimum_candidate_grounding_alignment": (
                round(min(grounding_minimums), 4)
                if grounding_minimums
                else None
            ),
            "highest_candidate_pair_similarity": (
                round(max(highest_pair_similarities), 4)
                if highest_pair_similarities
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
            "quality_warning_case_count": quality_warning_case_count,
            "quality_warning_counts": dict(
                sorted(quality_warning_counts.items())
            ),
            "promotion_eligibility_counts": promotion_status_counts,
            "semantic_diversification_repair_counts": (
                diversification_repair_counts
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
