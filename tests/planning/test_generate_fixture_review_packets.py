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
        "adversarial_cloud_incident_health_near_miss",
        "sparse_evidence_cloud_cost",
    )
