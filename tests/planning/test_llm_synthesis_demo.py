from pathlib import Path

from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    ROUTING_APPROVED,
)
from planning.llm_synthesis_demo import (
    build_default_output_path,
    build_default_validation_report_path,
    run_llm_synthesis_demo,
    write_synthesis_demo_output,
)


ARTIFACT_PATH = Path(
    "data/manual_fixture_artifacts/deterministic_template_risk/"
    "1bc94b0f56984302922f13d42dcb2a2e.json"
)


def test_llm_synthesis_demo_defaults_to_dry_run_without_api_call():
    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
    )

    assert result["fixture_id"] == "deterministic_template_risk"
    assert result["mode"] == DEEP_MODE
    assert result["provider"] == "fake-dry-run"
    assert result["dry_run"] is True
    assert result["api_call_attempted"] is False
    assert result["routing_decision"]["should_route"] is True
    assert result["routing_decision"]["reason"] == ROUTING_APPROVED
    assert result["token_estimate"]["estimated_tokens"] > 0
    assert result["response"]["parsed_response"] is not None


def test_llm_synthesis_demo_does_not_call_provider_when_routing_blocks():
    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        mode=FAST_MODE,
    )

    assert result["routing_decision"]["should_route"] is False
    assert result["response"]["raw_response_text"] == ""
    assert result["response"]["warnings"] == (
        "routing_decision_blocked_synthesis",
    )


def test_llm_synthesis_demo_marks_openai_api_attempt_only_when_not_dry_run():
    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        provider_name="openai",
        dry_run=True,
    )

    assert result["provider"] == "fake-dry-run"
    assert result["api_call_attempted"] is False



def test_llm_synthesis_demo_can_write_output_file(tmp_path):
    output_path = tmp_path / "synthesis_output.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )

    assert output_path.exists()
    assert result["run_metadata"]["artifact_path"] == str(ARTIFACT_PATH)
    assert "created_at_utc" in result["run_metadata"]
    assert "parsed_response" in result["response"]


def test_write_synthesis_demo_output_creates_parent_directories(tmp_path):
    output_path = tmp_path / "nested" / "result.json"
    result = {"hello": "world"}

    written_path = write_synthesis_demo_output(result, output_path)

    assert written_path == output_path
    assert output_path.exists()
    assert '"hello": "world"' in output_path.read_text()


def test_default_output_path_includes_run_identity():
    output_path = build_default_output_path(
        fixture_id="fixture",
        artifact_id="artifact",
        mode="deep",
        provider="openai",
        dry_run=False,
    )

    assert output_path.parent == Path("outputs/llm_synthesis_runs")
    assert "fixture_artifact_deep_openai_real_" in output_path.name
    assert output_path.suffix == ".json"



def test_llm_synthesis_demo_dry_run_uses_scoped_three_direction_schema():
    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
    )

    directions = result["response"]["parsed_response"]["project_directions"]

    assert [direction["scope_level"] for direction in directions] == [
        "easy",
        "medium",
        "hard",
    ]
    assert [direction["build_type"] for direction in directions] == [
        "quick_build",
        "resume_mvp",
        "flagship_extension",
    ]
    assert [direction["estimated_time"] for direction in directions] == [
        "1-2 days",
        "3-5 days",
        "1-2 weeks",
    ]



def test_llm_synthesis_demo_records_saved_output_validation(tmp_path):
    output_path = tmp_path / "synthesis_output.json"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
    )

    validation = result["saved_output_validation"]

    assert output_path.exists()
    assert "is_valid" in validation
    assert "errors" in validation
    assert "invented_source_ids" in validation
    assert not validation["is_valid"]
    assert "project_direction_0_missing_source_ids" in validation["errors"]



def test_build_default_validation_report_path():
    synthesis_output_path = Path(
        "outputs/llm_synthesis_runs/sample_output.json"
    )

    report_path = build_default_validation_report_path(
        synthesis_output_path=synthesis_output_path,
        report_dir=Path("outputs/reports"),
    )

    assert report_path == Path(
        "outputs/reports/sample_output_validation_report.md"
    )


def test_llm_synthesis_demo_writes_validation_report(tmp_path):
    output_path = tmp_path / "synthesis_output.json"
    report_path = tmp_path / "validation_report.md"

    result = run_llm_synthesis_demo(
        artifact_path=ARTIFACT_PATH,
        output_path=output_path,
        validation_report_output_path=report_path,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert result["validation_report_output_path"] == str(report_path)
    assert "LLM Synthesis Validation Report" in report_path.read_text()
