import pytest

from planning.fixture_review_oracles import (
    fixture_review_oracles,
    get_fixture_review_oracle,
)


def test_fixture_review_oracles_are_valid():
    oracles = fixture_review_oracles()

    assert len(oracles) == 1

    oracle = oracles[0]
    oracle.validate()

    assert oracle.fixture_id == "sparse_evidence_cloud_cost"
    assert oracle.expected_overall_preference == "both_weak"
    assert oracle.expected_response_quality == "exploratory"


def test_fixture_review_oracle_rejects_unknown_fixture():
    with pytest.raises(ValueError, match="No review oracle"):
        get_fixture_review_oracle("unknown_fixture")
