from typing import Any, Dict, List, Sequence


def evaluate_labeled_ranking(
    scored_candidates: Sequence[Dict[str, Any]],
    score_field: str = "raw_cosine",
) -> Dict[str, Any]:
    """
    Evaluate whether higher human relevance labels receive higher
    semantic scores. Labels are evaluation-only and never affect
    production scoring.
    """
    candidates: List[Dict[str, Any]] = [
        {
            "candidate_id": str(candidate["candidate_id"]),
            "label": int(candidate["label"]),
            "score": float(candidate[score_field]),
        }
        for candidate in scored_candidates
    ]

    ordered_pair_count = 0
    correct_pair_count = 0
    tie_pair_count = 0

    for index, left in enumerate(candidates):
        for right in candidates[index + 1:]:
            if left["label"] == right["label"]:
                continue

            ordered_pair_count += 1

            higher_label, lower_label = (
                (left, right)
                if left["label"] > right["label"]
                else (right, left)
            )

            if higher_label["score"] > lower_label["score"]:
                correct_pair_count += 1
            elif higher_label["score"] == lower_label["score"]:
                tie_pair_count += 1

    ranked_candidates = sorted(
        candidates,
        key=lambda candidate: candidate["score"],
        reverse=True,
    )

    top_candidate = ranked_candidates[0] if ranked_candidates else None

    return {
        "score_field": score_field,
        "candidate_count": len(candidates),
        "ordered_pair_count": ordered_pair_count,
        "correct_pair_count": correct_pair_count,
        "tie_pair_count": tie_pair_count,
        "pairwise_accuracy": (
            round(correct_pair_count / ordered_pair_count, 4)
            if ordered_pair_count
            else 0.0
        ),
        "top_candidate_id": (
            top_candidate["candidate_id"] if top_candidate else None
        ),
        "top_candidate_label": (
            top_candidate["label"] if top_candidate else None
        ),
    }


def evaluate_labeled_rankings(
    rankings: Dict[str, Sequence[Dict[str, Any]]],
    score_field: str = "raw_cosine",
) -> Dict[str, Any]:
    """
    Aggregate evaluation-only semantic ranking results across goals.
    """
    goal_reports = {
        goal_id: evaluate_labeled_ranking(
            scored_candidates,
            score_field=score_field,
        )
        for goal_id, scored_candidates in rankings.items()
    }

    total_ordered_pair_count = sum(
        report["ordered_pair_count"]
        for report in goal_reports.values()
    )
    total_correct_pair_count = sum(
        report["correct_pair_count"]
        for report in goal_reports.values()
    )
    total_tie_pair_count = sum(
        report["tie_pair_count"]
        for report in goal_reports.values()
    )

    return {
        "score_field": score_field,
        "evaluated_goal_count": len(goal_reports),
        "total_ordered_pair_count": total_ordered_pair_count,
        "total_correct_pair_count": total_correct_pair_count,
        "total_tie_pair_count": total_tie_pair_count,
        "overall_pairwise_accuracy": (
            round(
                total_correct_pair_count / total_ordered_pair_count,
                4,
            )
            if total_ordered_pair_count
            else 0.0
        ),
        "goal_reports": goal_reports,
    }


def evaluate_semantic_goal_dataset(
    dataset: Dict[str, Any],
    encoder: Any,
) -> Dict[str, Any]:
    """
    Score labeled evaluation cases with the semantic goal scorer.

    Dataset labels are used only to evaluate ordering quality. They never
    influence production candidate scoring or selection.
    """
    from planning.candidate_models import (
        CandidateDirection,
        CandidateGenerationRequest,
    )
    from planning.semantic_goal_relevance import (
        GoalRelevanceScorer,
    )

    scorer = GoalRelevanceScorer(encoder)
    rankings: Dict[str, List[Dict[str, Any]]] = {}

    for case in dataset.get("cases", []):
        goal_id = str(case["id"])
        request = CandidateGenerationRequest(
            user_goal=str(case["user_goal"]),
            skill_level=str(case.get("skill_level", "")),
            time_available=str(case.get("time_available", "")),
            target_roles=list(case.get("target_roles", [])),
            preferred_stack=list(case.get("preferred_stack", [])),
        )

        candidate_entries = list(case.get("candidates", []))
        candidates = [
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

        scored_results = scorer.score_candidates(request, candidates)

        rankings[goal_id] = [
            {
                "candidate_id": str(entry["id"]),
                "label": int(entry["label"]),
                "raw_cosine": result.trace.raw_cosine,
            }
            for entry, result in zip(candidate_entries, scored_results)
        ]

    return evaluate_labeled_rankings(rankings)


def evaluate_cross_encoder_goal_dataset(
    dataset: Dict[str, Any],
    pair_scorer: Any,
) -> Dict[str, Any]:
    """
    Evaluate cross-encoder goal/candidate ordering against labels.

    Labels are evaluation-only and never affect production ranking.
    """
    from planning.candidate_models import (
        CandidateDirection,
        CandidateGenerationRequest,
    )
    from planning.cross_encoder_goal_relevance import (
        CrossEncoderGoalRelevanceScorer,
    )

    scorer = CrossEncoderGoalRelevanceScorer(pair_scorer)
    rankings: Dict[str, List[Dict[str, Any]]] = {}

    for case in dataset.get("cases", []):
        goal_id = str(case["id"])
        request = CandidateGenerationRequest(
            user_goal=str(case["user_goal"]),
            skill_level=str(case.get("skill_level", "")),
            time_available=str(case.get("time_available", "")),
            target_roles=list(case.get("target_roles", [])),
            preferred_stack=list(case.get("preferred_stack", [])),
        )

        candidate_entries = list(case.get("candidates", []))
        candidates = [
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

        scored_results = scorer.score_candidates(request, candidates)

        rankings[goal_id] = [
            {
                "candidate_id": str(entry["id"]),
                "label": int(entry["label"]),
                "cross_encoder_score": result.raw_score,
            }
            for entry, result in zip(candidate_entries, scored_results)
        ]

    return evaluate_labeled_rankings(
        rankings,
        score_field="cross_encoder_score",
    )
