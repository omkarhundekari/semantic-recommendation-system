from pathlib import Path

from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    ROUTING_APPROVED,
)
from planning.llm_synthesis_demo import (
    build_default_output_path,
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
