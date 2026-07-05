import pytest

from planning.shadow_fixture_registry import (
    fixture_cases,
    select_fixture_cases,
)


def test_registry_has_ten_unique_rubric_driven_cases():
    cases = fixture_cases()

    assert len(cases) == 10
    assert len({case.case_id for case in cases}) == 10

    required_tags = {
        "strong_direct",
        "sparse",
        "ambiguous_query",
        "adversarial_near_miss",
        "deterministic_risk",
        "strict_scope",
    }
    actual_tags = {
        tag
        for case in cases
        for tag in case.coverage_tags
    }

    assert required_tags.issubset(actual_tags)

    for case in cases:
        assert case.user_goal
        assert case.evaluation_hypotheses
        assert case.reviewer_focus
        case.validate()


def test_registry_selects_requested_cases_and_rejects_unknown_ids():
    selected = select_fixture_cases(
        [
            "data_quality_strong_direct",
            "strict_weekend_scope",
        ]
    )

    assert [case.case_id for case in selected] == [
        "data_quality_strong_direct",
        "strict_weekend_scope",
    ]

    with pytest.raises(ValueError, match="Unknown fixture case IDs"):
        select_fixture_cases(["does_not_exist"])


def test_registry_cases_serialize_without_claiming_outcomes():
    payload = fixture_cases()[-1].to_dict()

    assert "evaluation_hypotheses" in payload
    assert "expected_winner" not in payload
    assert "planner_outcome" not in payload
