import pytest

from planning.manual_review_rubric import (
    ManualCandidateReview,
    ManualReviewRecord,
    ManualSetReview,
)
from planning.manual_review_store import (
    append_manual_review_record,
    build_stored_manual_review_record,
    load_manual_review_records,
)


def _artifact():
    return {
        "artifact_identity": {
            "artifact_id": "a" * 32,
            "fixture_id": "sparse_evidence_cloud_cost",
        },
        "v2_shadow": {
            "generation_metadata": {
                "prompt_content_hash": "b" * 64,
            },
            "manual_review_template": {
                "rubric_version": "v1",
                "query_fingerprint": "fixture-query",
                "deterministic_review": {
                    "candidate_reviews": [
                        {"candidate_title": "Template Planner"}
                    ]
                },
                "openai_review": {
                    "candidate_reviews": [
                        {"candidate_title": "Cost Explorer"}
                    ]
                },
            },
        },
    }


def _completed_review():
    return ManualReviewRecord(
        rubric_version="v1",
        query_fingerprint="fixture-query",
        deterministic_review=ManualSetReview(
            planner_path="deterministic",
            candidate_reviews=[
                ManualCandidateReview(
                    candidate_title="Template Planner",
                    goal_alignment=0,
                    grounding=0,
                    scope_realism=2,
                )
            ],
            distinctiveness=0,
        ),
        openai_review=ManualSetReview(
            planner_path="openai",
            candidate_reviews=[
                ManualCandidateReview(
                    candidate_title="Cost Explorer",
                    goal_alignment=1,
                    grounding=1,
                    scope_realism=2,
                )
            ],
            distinctiveness=1,
        ),
        overall_preference="both_weak",
        overall_preference_reason=(
            "Neither planner set has evidence strong enough for a "
            "confident root-cause recommendation."
        ),
        response_quality="exploratory",
        response_quality_reason=(
            "Only adjacent implementation and research context is available."
        ),
        unique_angle_quality="not_applicable",
        unique_angle_quality_reason=(
            "Semantic comparison was not assessed for this fixture."
        ),
    )


def test_builds_review_record_linked_to_exact_artifact():
    record = build_stored_manual_review_record(
        artifact=_artifact(),
        review=_completed_review(),
        reviewer_id="reviewer_a",
        artifact_path_hint=(
            "outputs/manual_fixture_reviews/"
            "sparse_evidence_cloud_cost/a.json"
        ),
        review_id="c" * 32,
        reviewed_at_utc="20260705T170000Z",
    )

    payload = record.to_dict()

    assert payload["artifact_id"] == "a" * 32
    assert payload["fixture_id"] == "sparse_evidence_cloud_cost"
    assert payload["prompt_content_hash"] == "b" * 64
    assert payload["rubric_version"] == "v1"
    assert payload["review"]["overall_preference"] == "both_weak"
    assert payload["review"]["response_quality"] == "exploratory"


def test_appends_and_loads_review_records_without_mutating_prior_rows(
    tmp_path,
):
    path = tmp_path / "manual_reviews.jsonl"

    first = build_stored_manual_review_record(
        artifact=_artifact(),
        review=_completed_review(),
        reviewer_id="reviewer_a",
        artifact_path_hint="artifact-a.json",
        review_id="c" * 32,
        reviewed_at_utc="20260705T170000Z",
    )
    second = build_stored_manual_review_record(
        artifact=_artifact(),
        review=_completed_review(),
        reviewer_id="reviewer_b",
        artifact_path_hint="artifact-a.json",
        review_id="d" * 32,
        reviewed_at_utc="20260705T170100Z",
        supersedes="c" * 32,
    )

    append_manual_review_record(first, path)
    original_contents = path.read_text()

    append_manual_review_record(second, path)
    records = load_manual_review_records(path)

    assert len(records) == 2
    assert path.read_text().startswith(original_contents)
    assert records[1].supersedes == "c" * 32


def test_rejects_duplicate_review_id_in_append_only_store(tmp_path):
    path = tmp_path / "manual_reviews.jsonl"

    record = build_stored_manual_review_record(
        artifact=_artifact(),
        review=_completed_review(),
        reviewer_id="reviewer_a",
        artifact_path_hint="artifact-a.json",
        review_id="c" * 32,
        reviewed_at_utc="20260705T170000Z",
    )

    append_manual_review_record(record, path)

    with pytest.raises(ValueError, match="already exists"):
        append_manual_review_record(record, path)


def test_rejects_review_that_does_not_match_artifact_template():
    review = _completed_review()

    mismatched = ManualReviewRecord(
        rubric_version=review.rubric_version,
        query_fingerprint="wrong-query",
        deterministic_review=review.deterministic_review,
        openai_review=review.openai_review,
        overall_preference=review.overall_preference,
        overall_preference_reason=review.overall_preference_reason,
        response_quality=review.response_quality,
        response_quality_reason=review.response_quality_reason,
        unique_angle_quality=review.unique_angle_quality,
        unique_angle_quality_reason=review.unique_angle_quality_reason,
    )

    with pytest.raises(ValueError, match="query fingerprint"):
        build_stored_manual_review_record(
            artifact=_artifact(),
            review=mismatched,
            reviewer_id="reviewer_a",
            artifact_path_hint="artifact-a.json",
        )
