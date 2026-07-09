from planning.generate_fixture_review_packets import (
    available_fixture_ids,
    build_fixture_artifact,
    render_review_packet,
    select_fixture_specifications,
    write_fixture_review_packets,
)


def test_selects_all_initial_fixture_specs_by_default():
    specs = select_fixture_specifications()

    assert [spec.case.case_id for spec in specs] == [
        "data_quality_strong_direct",
        "rag_qa_strong_direct",
        "developer_productivity_flaky_tests",
        "adversarial_cloud_incident_health_near_miss",
        "sparse_evidence_cloud_cost",
    ]


def test_rejects_unknown_fixture_specification():
    import pytest

    with pytest.raises(ValueError, match="Unknown fixture specification"):
        select_fixture_specifications(["missing_fixture"])


def test_review_packet_is_self_contained_and_does_not_include_oracle():
    spec = select_fixture_specifications(
        ["adversarial_cloud_incident_health_near_miss"]
    )[0]
    artifact = build_fixture_artifact(spec)

    packet = render_review_packet(
        artifact=artifact,
        specification=spec,
    )

    assert "# Manual Review Packet:" in packet
    assert "## Rubric" in packet
    assert "## Evidence Brief" in packet
    assert "Continuous Health Event Retrieval" in packet
    assert "Health Event Incident Correlator" in packet
    assert "## Candidate-to-Source Relevance Diagnostics" in packet
    assert "adjacent_context_only" in packet
    assert "## Quality Warnings" in packet
    assert "adjacent_context_only_candidate" in packet
    assert "both_weak" in packet
    assert "standard, limited, exploratory" in packet
    assert "expected_overall_preference" not in packet
    assert "expected_response_quality" not in packet


def test_writes_artifact_and_packet_for_selected_fixture(tmp_path):
    spec = select_fixture_specifications(
        ["sparse_evidence_cloud_cost"]
    )[0]

    written = write_fixture_review_packets(
        specifications=[spec],
        output_dir=tmp_path,
    )

    assert len(written) == 1
    assert written[0]["artifact_path"].exists()
    assert written[0]["packet_path"].exists()
    assert written[0]["artifact_path"].parent.name == (
        "sparse_evidence_cloud_cost"
    )

    packet = written[0]["packet_path"].read_text()

    assert "sparse_evidence_cloud_cost" in packet
    assert "## Artifact Identity" in packet
    assert "Cloud Cost Optimization Command Center" in packet

    artifact = __import__("json").loads(
        written[0]["artifact_path"].read_text()
    )

    assert artifact["artifact_identity"]["fixture_id"] == (
        "sparse_evidence_cloud_cost"
    )
    assert len(
        artifact["v2_shadow"]["generation_metadata"][
            "prompt_content_hash"
        ]
    ) == 64


def test_available_fixture_ids_match_selectable_specs():
    assert available_fixture_ids() == (
        "data_quality_strong_direct",
        "rag_qa_strong_direct",
        "developer_productivity_flaky_tests",
        "adversarial_cloud_incident_health_near_miss",
        "sparse_evidence_cloud_cost",
    )



def test_adversarial_warning_chain_reaches_review_packet():
    spec = select_fixture_specifications(
        ["adversarial_cloud_incident_health_near_miss"]
    )[0]
    artifact = build_fixture_artifact(spec)
    packet = render_review_packet(
        artifact=artifact,
        specification=spec,
    )

    relevance_traces = artifact["v2_shadow"][
        "candidate_source_relevance"
    ]
    quality_warnings = artifact["v2_shadow"]["quality_warnings"]

    health_trace = next(
        trace
        for trace in relevance_traces
        if trace["candidate_title"] == "Health Event Incident Correlator"
    )

    warning_codes = {
        warning["code"]
        for warning in quality_warnings["warnings"]
    }

    assert health_trace["source_id"] == "paper-health-events"
    assert health_trace["relevance_status"] == "adjacent_context_only"
    assert "adjacent_context_only_candidate" in warning_codes

    assert "## Candidate-to-Source Relevance Diagnostics" in packet
    assert "Health Event Incident Correlator" in packet
    assert "paper-health-events" in packet
    assert "adjacent_context_only" in packet

    assert "## Quality Warnings" in packet
    assert "adjacent_context_only_candidate" in packet



def test_rag_fixture_review_packet_uses_predeclared_oracle_but_hides_it():
    spec = select_fixture_specifications(["rag_qa_strong_direct"])[0]
    artifact = build_fixture_artifact(spec)
    packet = render_review_packet(
        artifact=artifact,
        specification=spec,
    )

    assert "rag_qa_strong_direct" in packet
    assert "RAG QA Citation Quality Workbench" in packet
    assert "RAG Retrieval Failure Analyzer" in packet
    assert "Question-Level RAG Evaluation Dashboard" in packet
    assert "Citation Grounding" in packet
    assert "Question Answering" in packet
    assert "expected_overall_preference" not in packet
    assert "expected_response_quality" not in packet



def test_flaky_tests_review_packet_uses_predeclared_oracle_but_hides_it():
    spec = select_fixture_specifications(
        ["developer_productivity_flaky_tests"]
    )[0]
    artifact = build_fixture_artifact(spec)
    packet = render_review_packet(
        artifact=artifact,
        specification=spec,
    )

    assert "developer_productivity_flaky_tests" in packet
    assert "Flaky Test Detection Dashboard" in packet
    assert "Code Change Failure Correlator" in packet
    assert "CI Root Cause Prioritization Queue" in packet
    assert "flaky tests" in packet.lower()
    assert "code changes" in packet.lower()
    assert "root cause" in packet.lower()
    assert "expected_overall_preference" not in packet
    assert "expected_response_quality" not in packet
