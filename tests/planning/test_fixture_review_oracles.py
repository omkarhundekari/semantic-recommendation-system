import pytest

from planning.fixture_review_oracles import (
    fixture_review_oracles,
    get_fixture_review_oracle,
)


def test_fixture_review_oracles_are_valid():
    oracles = fixture_review_oracles()

    assert len(oracles) == 10
    assert len({oracle.fixture_id for oracle in oracles}) == len(oracles)

    for oracle in oracles:
        oracle.validate()

    sparse_oracle = get_fixture_review_oracle(
        "sparse_evidence_cloud_cost"
    )

    assert sparse_oracle.expected_overall_preference == "both_weak"
    assert sparse_oracle.expected_response_quality == "exploratory"


def test_fixture_review_oracle_rejects_unknown_fixture():
    with pytest.raises(ValueError, match="No review oracle"):
        get_fixture_review_oracle("unknown_fixture")
