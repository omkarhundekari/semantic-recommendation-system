from planning.manual_review_rubric import (
    ManualCandidateReview,
    ManualReviewRecord,
    ManualSetReview,
)
from planning.manual_review_store import StoredManualReviewRecord
from planning.manual_review_summary import build_manual_review_summary


def _review(preference, response_quality):
    candidate = ManualCandidateReview(
        candidate_title="Candidate",
        goal_alignment=1,
        grounding=1,
        scope_realism=1,
        notes="Review note.",
    )

    return ManualReviewRecord(
        rubric_version="v1",
        query_fingerprint="query-fingerprint",
        deterministic_review=ManualSetReview(
            planner_path="deterministic",
            candidate_reviews=[candidate],
            distinctiveness=1,
            notes="Deterministic notes.",
        ),
        openai_review=ManualSetReview(
            planner_path="openai",
            candidate_reviews=[candidate],
            distinctiveness=1,
            notes="Shadow notes.",
        ),
        overall_preference=preference,
        overall_preference_reason="Preference reason.",
        response_quality=response_quality,
        response_quality_reason="Quality reason.",
        unique_angle_quality="not_applicable",
        unique_angle_quality_reason="No comparison encoder.",
        reviewer_notes="Reviewer notes.",
    )


def _stored(
    fixture_id,
    artifact_id,
    review_id,
    reviewed_at_utc,
    preference,
    response_quality,
):
    return StoredManualReviewRecord(
        review_id=review_id,
        artifact_id=artifact_id,
        fixture_id=fixture_id,
        artifact_path_hint=f"data/{artifact_id}.json",
        prompt_content_hash="a" * 64,
        reviewer_id="reviewer_a",
        reviewed_at_utc=reviewed_at_utc,
        review=_review(preference, response_quality),
    )


def test_summary_preserves_each_artifact_review_and_latest_fixture_view():
    summary = build_manual_review_summary(
        [
            _stored(
                "fixture-a",
                "artifact-old",
                "review-old",
                "20260705T170000Z",
                "openai",
                "limited",
            ),
            _stored(
                "fixture-a",
                "artifact-new",
                "review-new",
                "20260705T171000Z",
                "openai",
                "standard",
            ),
            _stored(
                "fixture-b",
                "artifact-b",
                "review-b",
                "20260705T172000Z",
                "both_weak",
                "exploratory",
            ),
        ]
    )

    assert summary["review_record_count"] == 3
    assert summary["fixture_count"] == 2
    assert summary["preference_counts"] == {
        "both_weak": 1,
        "openai": 2,
    }
    assert summary["response_quality_counts"] == {
        "exploratory": 1,
        "limited": 1,
        "standard": 1,
    }

    assert len(summary["artifact_reviews"]) == 3
    assert len(summary["latest_review_by_fixture"]) == 2

    latest_artifacts = {
        row["artifact_id"]
        for row in summary["latest_review_by_fixture"]
    }
    assert latest_artifacts == {"artifact-new", "artifact-b"}

    old_row = next(
        row
        for row in summary["artifact_reviews"]
        if row["artifact_id"] == "artifact-old"
    )
    assert old_row["is_latest_for_fixture"] is False
