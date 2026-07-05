from types import SimpleNamespace

from planning.fixture_review_oracles import FixtureReviewOracle
from planning.fixture_review_oracle_comparison import (
    build_fixture_review_oracle_comparison,
)


def _record(
    fixture_id,
    artifact_id,
    review_id,
    reviewed_at_utc,
    preference,
    response_quality,
):
    return SimpleNamespace(
        fixture_id=fixture_id,
        artifact_id=artifact_id,
        review_id=review_id,
        reviewed_at_utc=reviewed_at_utc,
        review=SimpleNamespace(
            overall_preference=preference,
            response_quality=response_quality,
        ),
    )


def test_comparison_uses_latest_review_and_preserves_missing_states():
    records = [
        _record(
            "sparse_evidence_cloud_cost",
            "artifact-old",
            "review-old",
            "20260705T170000Z",
            "openai",
            "limited",
        ),
        _record(
            "sparse_evidence_cloud_cost",
            "artifact-new",
            "review-new",
            "20260705T171000Z",
            "both_weak",
            "exploratory",
        ),
        _record(
            "adversarial_cloud_incident_health_near_miss",
            "artifact-adversarial",
            "review-adversarial",
            "20260705T172000Z",
            "openai",
            "limited",
        ),
    ]

    oracles = [
        FixtureReviewOracle(
            fixture_id="sparse_evidence_cloud_cost",
            expected_overall_preference="both_weak",
            expected_response_quality="exploratory",
            reviewer_expectations=("Allow both_weak.",),
            rationale="Sparse evidence should remain exploratory.",
        ),
        FixtureReviewOracle(
            fixture_id="data_quality_strong_direct",
            expected_overall_preference="openai",
            expected_response_quality="standard",
            reviewer_expectations=("Strong evidence should be reviewable.",),
            rationale="Direct evidence should support standard quality.",
        ),
    ]

    comparison = build_fixture_review_oracle_comparison(
        records=records,
        oracles=oracles,
    )

    assert comparison["latest_review_fixture_count"] == 2
    assert comparison["oracle_fixture_count"] == 2
    assert comparison["comparison_counts"] == {
        "matched": 1,
        "missing_oracle": 1,
        "missing_review": 1,
    }

    rows = {
        row["fixture_id"]: row
        for row in comparison["rows"]
    }

    assert rows["sparse_evidence_cloud_cost"]["status"] == "matched"
    assert rows["sparse_evidence_cloud_cost"]["artifact_id"] == "artifact-new"

    assert (
        rows["adversarial_cloud_incident_health_near_miss"]["status"]
        == "missing_oracle"
    )
    assert rows["data_quality_strong_direct"]["status"] == "missing_review"
