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
        "rag_qa_strong_direct",
        "developer_productivity_flaky_tests",
        "adversarial_cloud_incident_health_near_miss",
        "strict_weekend_scope",
        "sparse_evidence_cloud_cost",
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
        "rag_qa_strong_direct",
        "developer_productivity_flaky_tests",
        "adversarial_cloud_incident_health_near_miss",
        "strict_weekend_scope",
        "sparse_evidence_cloud_cost",
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



def test_sparse_fixture_oracle_is_separate_from_generated_artifact():
    import json

    from planning.fixture_review_oracles import (
        get_fixture_review_oracle,
    )

    spec = get_fixture_specification("sparse_evidence_cloud_cost")
    oracle = get_fixture_review_oracle(spec.case.case_id)

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    serialized_artifact = json.dumps(artifact)

    assert oracle.expected_overall_preference == "both_weak"
    assert oracle.expected_response_quality == "exploratory"
    assert "expected_overall_preference" not in serialized_artifact
    assert "expected_response_quality" not in serialized_artifact



def test_adversarial_fixture_emits_adjacent_context_relevance_trace():
    spec = get_fixture_specification(
        "adversarial_cloud_incident_health_near_miss"
    )

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    trace = next(
        item
        for item in artifact["v2_shadow"]["candidate_source_relevance"]
        if (
            item["candidate_title"]
            == "Health Event Incident Correlator"
        )
    )

    assert trace["source_id"] == "paper-health-events"
    assert trace["relevance_status"] == "adjacent_context_only"



def test_adversarial_fixture_quality_warnings_flag_adjacent_only_candidate():
    spec = get_fixture_specification(
        "adversarial_cloud_incident_health_near_miss"
    )

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    warnings = {
        warning["code"]: warning
        for warning in artifact["v2_shadow"]["quality_warnings"][
            "warnings"
        ]
    }

    assert "adjacent_context_only_candidate" in warnings
    assert warnings[
        "adjacent_context_only_candidate"
    ]["details"]["candidates"][0]["candidate_title"] == (
        "Health Event Incident Correlator"
    )



def test_rag_fixture_has_predeclared_oracle_and_qa_specific_evidence():
    import json

    from planning.fixture_review_oracles import (
        get_fixture_review_oracle,
    )

    spec = get_fixture_specification("rag_qa_strong_direct")
    oracle = get_fixture_review_oracle(spec.case.case_id)

    source_titles = {
        item["title"]
        for item in spec.evidence_payload["merged_results"]
    }

    assert oracle.expected_overall_preference == "openai"
    assert oracle.expected_response_quality == "standard"
    assert any("Question Answering" in title for title in source_titles)
    assert any("Citation Grounding" in title for title in source_titles)

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    serialized_artifact = json.dumps(artifact)

    assert "RAG QA Citation Quality Workbench" in serialized_artifact
    assert "RAG Retrieval Failure Analyzer" in serialized_artifact
    assert "Question-Level RAG Evaluation Dashboard" in serialized_artifact
    assert "expected_overall_preference" not in serialized_artifact
    assert "expected_response_quality" not in serialized_artifact



def test_flaky_tests_fixture_has_predeclared_oracle_and_multi_anchor_evidence():
    import json

    from planning.fixture_review_oracles import (
        get_fixture_review_oracle,
    )

    spec = get_fixture_specification("developer_productivity_flaky_tests")
    oracle = get_fixture_review_oracle(spec.case.case_id)

    source_titles = {
        item["title"]
        for item in spec.evidence_payload["merged_results"]
    }

    assert oracle.expected_overall_preference == "openai"
    assert oracle.expected_response_quality == "standard"
    assert any("Flaky Tests" in title for title in source_titles)
    assert any("Code Changes" in title for title in source_titles)
    assert any("CI Failure" in title for title in source_titles)

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    serialized_artifact = json.dumps(artifact)

    assert "Flaky Test Detection Dashboard" in serialized_artifact
    assert "Code Change Failure Correlator" in serialized_artifact
    assert "CI Root Cause Prioritization Queue" in serialized_artifact
    assert "expected_overall_preference" not in serialized_artifact
    assert "expected_response_quality" not in serialized_artifact



def test_strict_weekend_fixture_has_predeclared_oracle_and_scope_evidence():
    import json

    from planning.fixture_review_oracles import (
        get_fixture_review_oracle,
    )

    spec = get_fixture_specification("strict_weekend_scope")
    oracle = get_fixture_review_oracle(spec.case.case_id)

    source_titles = {
        item["title"]
        for item in spec.evidence_payload["merged_results"]
    }

    assert oracle.expected_overall_preference == "tie"
    assert oracle.expected_response_quality == "limited"
    assert any("Lineage" in title for title in source_titles)
    assert any("Remediation" in title for title in source_titles)

    artifact = build_shadow_comparison_artifact(
        evidence_payload=spec.evidence_payload,
        user_goal=spec.case.user_goal,
        constraints=spec.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=spec.mock_response
        ),
    )

    serialized_artifact = json.dumps(artifact)

    assert "Weekend Lineage Impact Mapper" in serialized_artifact
    assert "Incident Owner Lookup Table" in serialized_artifact
    assert "Simple Remediation Priority Ranker" in serialized_artifact
    assert "expected_overall_preference" not in serialized_artifact
    assert "expected_response_quality" not in serialized_artifact
