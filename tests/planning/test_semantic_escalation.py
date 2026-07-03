from planning.semantic_escalation import (
    build_low_margin_escalation_details,
    select_low_margin_candidate_keys,
)
from planning.semantic_goal_relevance import (
    GoalRelevanceResult,
    GoalRelevanceTrace,
)


def make_result(candidate_key, raw_cosine):
    return GoalRelevanceResult(
        candidate_key=candidate_key,
        score=(raw_cosine + 1.0) / 2.0,
        trace=GoalRelevanceTrace(
            candidate_key=candidate_key,
            candidate_title=candidate_key,
            raw_cosine=raw_cosine,
            normalized_score=(raw_cosine + 1.0) / 2.0,
            goal_text_used="Goal",
            candidate_text_used="Candidate",
        ),
    )


def test_escalates_top_candidates_within_configured_margin():
    results = [
        make_result("direct", 0.70),
        make_result("near_miss", 0.67),
        make_result("weaker", 0.40),
        make_result("unrelated", 0.10),
    ]

    assert select_low_margin_candidate_keys(
        results=results,
        top_k=3,
        margin_threshold=0.05,
    ) == {"direct", "near_miss"}


def test_does_not_escalate_clear_winner_or_candidates_below_top_k():
    results = [
        make_result("winner", 0.80),
        make_result("adjacent", 0.60),
        make_result("weak", 0.58),
        make_result("outside_top_k", 0.30),
    ]

    assert select_low_margin_candidate_keys(
        results=results,
        top_k=3,
        margin_threshold=0.05,
    ) == set()


def test_empty_results_return_empty_set():
    assert select_low_margin_candidate_keys(
        results=[],
        top_k=3,
        margin_threshold=0.05,
    ) == set()


def test_low_margin_escalation_details_include_rank_margin_and_cohort():
    from planning.semantic_escalation import (
        build_low_margin_escalation_details,
    )

    results = [
        make_result("direct", 0.70),
        make_result("near_miss", 0.67),
        make_result("weak", 0.40),
    ]

    details = build_low_margin_escalation_details(
        results=results,
        top_k=3,
        margin_threshold=0.05,
    )

    assert details["direct"]["embedding_rank"] == 1
    assert details["direct"]["top_embedding_margin"] == 0.0
    assert details["direct"]["cohort_size"] == 3
    assert details["direct"]["escalated"] is True

    assert details["near_miss"]["embedding_rank"] == 2
    assert details["near_miss"]["top_embedding_margin"] == 0.03
    assert details["near_miss"]["escalated"] is True

    assert details["weak"]["embedding_rank"] == 3
    assert details["weak"]["escalated"] is False


def test_single_candidate_does_not_escalate_without_competition():
    details = build_low_margin_escalation_details(
        results=[make_result("only_candidate", 0.77)],
        top_k=3,
        margin_threshold=0.05,
    )

    assert details["only_candidate"]["embedding_rank"] == 1
    assert details["only_candidate"]["cohort_size"] == 1
    assert details["only_candidate"]["escalated"] is False


def test_clear_winner_does_not_escalate_without_close_competitor():
    details = build_low_margin_escalation_details(
        results=[
            make_result("winner", 0.80),
            make_result("adjacent", 0.60),
            make_result("weak", 0.30),
        ],
        top_k=3,
        margin_threshold=0.05,
    )

    assert details["winner"]["escalated"] is False
    assert details["adjacent"]["escalated"] is False
    assert details["weak"]["escalated"] is False
