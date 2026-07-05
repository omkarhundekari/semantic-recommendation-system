import pytest

from planning.manual_review_rubric import (
    ManualCandidateReview,
    ManualReviewRecord,
    ManualReviewRubric,
    ManualSetReview,
    build_manual_review_template,
)


def test_builds_unscored_template_from_comparison_payload():
    record = build_manual_review_template(
        {
            "query_fingerprint": "case-123",
            "deterministic_candidates": [
                {"title": "Pipeline Monitor"},
                {"title": "Warehouse Cost Dashboard"},
            ],
            "openai_candidates": [
                {"title": "Lineage Blast Radius Explorer"},
            ],
        }
    )

    payload = record.to_dict()

    assert payload["rubric_version"] == "v1"
    assert payload["query_fingerprint"] == "case-123"
    assert [
        item["candidate_title"]
        for item in payload["deterministic_review"]["candidate_reviews"]
    ] == [
        "Pipeline Monitor",
        "Warehouse Cost Dashboard",
    ]
    assert payload["openai_review"]["candidate_reviews"][0][
        "candidate_title"
    ] == "Lineage Blast Radius Explorer"
    assert payload["overall_preference"] is None


def test_accepts_both_weak_and_unique_angle_quality_review():
    record = ManualReviewRecord(
        rubric_version="v1",
        query_fingerprint="case-456",
        deterministic_review=ManualSetReview(
            planner_path="deterministic",
            candidate_reviews=[
                ManualCandidateReview(
                    candidate_title="Pipeline Monitor",
                    goal_alignment=1,
                    grounding=1,
                    scope_realism=2,
                )
            ],
            distinctiveness=1,
        ),
        openai_review=ManualSetReview(
            planner_path="openai",
            candidate_reviews=[
                ManualCandidateReview(
                    candidate_title="Lineage Explorer",
                    goal_alignment=0,
                    grounding=1,
                    scope_realism=1,
                )
            ],
            distinctiveness=2,
        ),
        overall_preference="both_weak",
        overall_preference_reason=(
            "Neither planner set directly addresses the requested workflow."
        ),
        unique_angle_quality="worse",
        unique_angle_quality_reason=(
            "The unique angle is less aligned with the specific user goal."
        ),
    )

    payload = record.to_dict()

    assert payload["overall_preference"] == "both_weak"
    assert payload["unique_angle_quality"] == "worse"


def test_rejects_invalid_scores_and_missing_review_reasons():
    with pytest.raises(ValueError, match="goal_alignment"):
        ManualCandidateReview(
            candidate_title="Invalid Candidate",
            goal_alignment=3,
        ).to_dict()

    with pytest.raises(ValueError, match="overall_preference_reason"):
        ManualReviewRecord(
            rubric_version="v1",
            query_fingerprint="case-789",
            deterministic_review=ManualSetReview(
                planner_path="deterministic"
            ),
            openai_review=ManualSetReview(
                planner_path="openai"
            ),
            overall_preference="openai",
        ).to_dict()


def test_rejects_duplicate_titles_within_a_planner_set():
    review = ManualSetReview(
        planner_path="openai",
        candidate_reviews=[
            ManualCandidateReview(candidate_title="Lineage Explorer"),
            ManualCandidateReview(candidate_title="lineage explorer"),
        ],
    )

    with pytest.raises(ValueError, match="duplicate"):
        review.to_dict()


def test_rubric_is_serializable_and_versioned():
    rubric = ManualReviewRubric()

    assert rubric.to_dict()["version"] == "v1"
    assert "goal_alignment_instruction" in rubric.to_dict()
