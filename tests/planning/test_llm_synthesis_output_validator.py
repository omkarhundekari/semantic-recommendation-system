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


def _make_scoped_directions(source_ids=None, confidence="Strong"):
    source_ids = source_ids or [
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
    ]

    base = {
        "title": "Scoped Project Direction",
        "problem_statement": "Build a grounded project from evidence cards.",
        "target_user": "students and early-career engineers",
        "why_this_is_grounded": "The cited source IDs appear in the evidence cards.",
        "source_ids": source_ids,
        "evidence_confidence": confidence,
        "grounding_warnings": ["No additional warning."],
        "mvp_scope": ["Build the core workflow."],
        "advanced_extensions": ["Add a stronger evaluation layer."],
        "skills_demonstrated": ["Python", "PostgreSQL"],
        "resume_bullet": "Built a grounded project synthesis workflow.",
        "interview_talking_points": ["Explain evidence-grounded synthesis."],
    }

    return [
        {
            **base,
            "scope_level": "easy",
            "build_type": "quick_build",
            "estimated_time": "1-2 days",
            "title": "Quick Build Direction",
        },
        {
            **base,
            "scope_level": "medium",
            "build_type": "resume_mvp",
            "estimated_time": "3-5 days",
            "title": "Resume MVP Direction",
        },
        {
            **base,
            "scope_level": "hard",
            "build_type": "flagship_extension",
            "estimated_time": "1-2 weeks",
            "title": "Flagship Extension Direction",
        },
    ]


def test_validator_accepts_saved_valid_synthesis_output(tmp_path):
    output_path = tmp_path / "valid_output.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"] = _make_scoped_directions()
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
    parsed["project_directions"] = _make_scoped_directions(
        source_ids=["made-up-source"]
    )
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
    parsed["project_directions"] = _make_scoped_directions(
        confidence="Very Strong"
    )
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



def test_validator_rejects_wrong_scoped_direction_sequence(tmp_path):
    output_path = tmp_path / "wrong_scope.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"] = _make_scoped_directions()
    parsed["project_directions"][0]["scope_level"] = "hard"
    parsed["overall_confidence"] = "Strong"
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert not validation.is_valid
    assert "project_direction_0_invalid_scope_level" in validation.errors



def test_validator_rejects_wrong_scoped_direction_sequence(tmp_path):
    output_path = tmp_path / "wrong_scope.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"] = _make_scoped_directions()
    parsed["project_directions"][0]["scope_level"] = "hard"
    parsed["overall_confidence"] = "Strong"
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    assert not validation.is_valid
    assert "project_direction_0_invalid_scope_level" in validation.errors



def test_validator_builds_grounding_trace_for_valid_sample_output():
    validation = validate_saved_synthesis_output(
        output_path=SAMPLE_VALID_OUTPUT,
    )

    traces = validation.direction_grounding_traces

    assert len(traces) == 3
    assert [trace["scope_level"] for trace in traces] == [
        "easy",
        "medium",
        "hard",
    ]
    assert all(trace["is_grounded"] for trace in traces)
    assert all(trace["invented_source_ids"] == [] for trace in traces)
    assert traces[0]["valid_cited_source_ids"] == [
        "paper-data-quality-impact",
        "paper-owner-aware-lineage",
        "repo-dashboard-impact",
    ]
    assert traces[0]["supporting_evidence_cards"][0]["source_id"] == (
        "paper-data-quality-impact"
    )


def test_validator_grounding_trace_exposes_invented_source_ids(tmp_path):
    output_path = tmp_path / "invented_source.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )
    parsed = result["response"]["parsed_response"]
    parsed["project_directions"] = _make_scoped_directions(
        source_ids=["made-up-source"]
    )
    parsed["overall_confidence"] = "Strong"
    result["response"]["raw_response_text"] = json.dumps(parsed)
    output_path.write_text(json.dumps(result, indent=2))

    validation = validate_saved_synthesis_output(
        output_path=output_path,
    )

    traces = validation.direction_grounding_traces

    assert not validation.is_valid
    assert traces[0]["is_grounded"] is False
    assert traces[0]["invented_source_ids"] == ["made-up-source"]
    assert traces[0]["valid_cited_source_ids"] == []
