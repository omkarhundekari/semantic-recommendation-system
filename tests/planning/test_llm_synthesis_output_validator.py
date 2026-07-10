import json
from pathlib import Path

from planning.llm_synthesis_demo import run_llm_synthesis_demo
from planning.llm_synthesis_output_validator import (
    validate_saved_synthesis_output,
)


ARTIFACT_PATH = Path(
    "data/manual_fixture_artifacts/deterministic_template_risk/"
    "1bc94b0f56984302922f13d42dcb2a2e.json"
)


def test_validator_accepts_saved_valid_synthesis_output(tmp_path):
    output_path = tmp_path / "valid_output.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"][0]["source_ids"] = [
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
    ]
    parsed["project_directions"][0]["evidence_confidence"] = "Strong"
    parsed["overall_confidence"] = "Strong"
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert validation.is_valid
    assert validation.errors == ()
    assert validation.invented_source_ids == ()
    assert validation.cited_source_ids == (
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
    )


def test_validator_rejects_invented_source_ids(tmp_path):
    output_path = tmp_path / "invented_source.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"][0]["source_ids"] = [
        "made-up-source",
    ]
    parsed["project_directions"][0]["evidence_confidence"] = "Strong"
    parsed["overall_confidence"] = "Strong"
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert not validation.is_valid
    assert "invented_source_ids" in validation.errors
    assert validation.invented_source_ids == ("made-up-source",)


def test_validator_rejects_invalid_json_parse_result(tmp_path):
    output_path = tmp_path / "invalid_parse.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    result["response"]["parsed_response"] = None
    result["response"]["warnings"] = ["invalid_json_response"]
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert not validation.is_valid
    assert "missing_parsed_response" in validation.errors
    assert "response_contains_warnings" in validation.errors


def test_validator_rejects_invalid_confidence_labels(tmp_path):
    output_path = tmp_path / "invalid_confidence.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["overall_confidence"] = "Very Strong"
    parsed["project_directions"][0]["evidence_confidence"] = "Very Strong"
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert not validation.is_valid
    assert "invalid_overall_confidence" in validation.errors
    assert (
        "project_direction_0_invalid_evidence_confidence"
        in validation.errors
    )



SAMPLE_VALID_OUTPUT = Path(
    "data/sample_llm_synthesis_outputs/valid_synthesis_sample.json"
)

SAMPLE_INVALID_TRUNCATED_OUTPUT = Path(
    "data/sample_llm_synthesis_outputs/invalid_truncated_sample.json"
)


def test_validator_accepts_committed_valid_sample_output():
    validation = validate_saved_synthesis_output(
        output_path=SAMPLE_VALID_OUTPUT,
    )

    assert validation.is_valid
    assert validation.errors == ()
    assert validation.invented_source_ids == ()
    assert validation.cited_source_ids == (
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
        "repo-dashboard-impact",
    )


def test_validator_rejects_committed_invalid_truncated_sample_output():
    validation = validate_saved_synthesis_output(
        output_path=SAMPLE_INVALID_TRUNCATED_OUTPUT,
    )

    assert not validation.is_valid
    assert "missing_parsed_response" in validation.errors
    assert "response_contains_warnings" in validation.errors
