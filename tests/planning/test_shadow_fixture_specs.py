import pytest

from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.shadow_comparison_demo import (
    build_shadow_comparison_artifact,
)
from planning.shadow_fixture_specs import (
    fixture_specifications,
    get_fixture_specification,
)


def test_first_fixture_specs_are_valid_and_match_registry_cases():
    specs = fixture_specifications()

    assert [spec.case.case_id for spec in specs] == [
        "data_quality_strong_direct",
        "adversarial_cloud_incident_health_near_miss",
    ]

    for spec in specs:
        spec.validate()
        assert len(spec.mock_response["candidates"]) == 3


def test_fixture_spec_rejects_unknown_case():
    with pytest.raises(ValueError, match="No fixture specification"):
        get_fixture_specification("unknown_case")


@pytest.mark.parametrize(
    "case_id",
    [
        "data_quality_strong_direct",
        "adversarial_cloud_incident_health_near_miss",
    ],
)
def test_fixture_specs_build_reviewable_artifacts(case_id):
    spec = get_fixture_specification(case_id)

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    shadow = artifact["v2_shadow"]
    template = shadow["manual_review_template"]

    assert shadow["raw_candidates"]
    assert shadow["enrichment"]["ideas"]
    assert shadow["shadow_vs_deterministic_comparison"]
    assert template["rubric_version"] == "v1"
    assert len(template["openai_review"]["candidate_reviews"]) == 3

    source_ids = {
        source["source_id"]
        for source in shadow["report"]["evidence_brief"]["sources"]
    }

    for candidate in shadow["raw_candidates"]:
        assert set(candidate["source_ids"]).issubset(source_ids)


def test_adversarial_fixture_keeps_near_miss_source_reviewable():
    spec = get_fixture_specification(
        "adversarial_cloud_incident_health_near_miss"
    )

    titles = {
        item["title"]
        for item in spec.evidence_payload["merged_results"]
    }

    assert "Continuous Health Event Retrieval" in titles

    near_miss_candidate = next(
        candidate
        for candidate in spec.mock_response["candidates"]
        if candidate["title"] == "Health Event Incident Correlator"
    )

    assert near_miss_candidate["source_ids"] == ["paper-health-events"]
