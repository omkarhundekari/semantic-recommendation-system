from pathlib import Path

from planning.llm_synthesis_batch_eval import (
    discover_artifact_paths,
    render_batch_synthesis_report,
    run_batch_synthesis_evaluation,
    summarize_batch_synthesis_results,
    write_batch_synthesis_report,
)


ARTIFACT_PATH = Path(
    "data/manual_fixture_artifacts/deterministic_template_risk/"
    "1bc94b0f56984302922f13d42dcb2a2e.json"
)


def test_discover_artifact_paths_finds_manual_fixture_artifacts():
    paths = discover_artifact_paths(
        artifact_dir=Path("data/manual_fixture_artifacts"),
    )

    assert ARTIFACT_PATH in paths
    assert all(path.suffix == ".json" for path in paths)


def test_batch_synthesis_evaluation_runs_fake_dry_run(tmp_path):
    batch_result = run_batch_synthesis_evaluation(
        artifact_paths=[ARTIFACT_PATH],
        output_dir=tmp_path / "runs",
        validation_report_dir=tmp_path / "reports",
    )

    summary = batch_result["summary"]

    assert summary["artifact_count"] == 1
    assert summary["routed_count"] == 1
    assert summary["blocked_count"] == 0
    assert summary["valid_count"] == 0
    assert summary["invalid_count"] == 1
    assert summary["invented_source_output_count"] == 0
    assert summary["grounded_direction_count"] == 0
    assert summary["ungrounded_direction_count"] == 3
    assert len(summary["output_paths"]) == 1
    assert len(summary["validation_report_paths"]) == 1
    assert Path(summary["output_paths"][0]).exists()
    assert Path(summary["validation_report_paths"][0]).exists()


def test_batch_synthesis_evaluation_can_run_without_saving():
    batch_result = run_batch_synthesis_evaluation(
        artifact_paths=[ARTIFACT_PATH],
        save_outputs=False,
    )

    summary = batch_result["summary"]

    assert summary["artifact_count"] == 1
    assert summary["output_paths"] == ()
    assert summary["validation_report_paths"] == ()


def test_summarize_batch_synthesis_results_counts_validation_outcomes():
    results = [
        {
            "routing_decision": {"should_route": True},
            "saved_output_validation": {
                "is_valid": True,
                "invented_source_ids": [],
                "output_path": "valid.json",
                "direction_grounding_traces": [
                    {"is_grounded": True},
                    {"is_grounded": False},
                ],
            },
            "validation_report_output_path": "valid.md",
        },
        {
            "routing_decision": {"should_route": False},
            "saved_output_validation": {
                "is_valid": False,
                "invented_source_ids": ["fake-source"],
                "output_path": "invalid.json",
                "direction_grounding_traces": [
                    {"is_grounded": False},
                ],
            },
            "validation_report_output_path": "invalid.md",
        },
    ]

    summary = summarize_batch_synthesis_results(results)

    assert summary.artifact_count == 2
    assert summary.routed_count == 1
    assert summary.blocked_count == 1
    assert summary.valid_count == 1
    assert summary.invalid_count == 1
    assert summary.invented_source_output_count == 1
    assert summary.grounded_direction_count == 1
    assert summary.ungrounded_direction_count == 2
    assert summary.output_paths == ("valid.json", "invalid.json")
    assert summary.validation_report_paths == ("valid.md", "invalid.md")



def test_render_batch_synthesis_report_includes_summary_and_fixture_results(tmp_path):
    batch_result = run_batch_synthesis_evaluation(
        artifact_paths=[ARTIFACT_PATH],
        output_dir=tmp_path / "runs",
        validation_report_dir=tmp_path / "reports",
    )

    report = render_batch_synthesis_report(batch_result)

    assert "# LLM Synthesis Batch Evaluation" in report
    assert "- Artifacts: 1" in report
    assert "- Routed: 1" in report
    assert "- Invalid outputs: 1" in report
    assert "## Fixture Results" in report
    assert "### deterministic_template_risk" in report
    assert "project_direction_0_missing_source_ids" in report


def test_write_batch_synthesis_report(tmp_path):
    batch_result = run_batch_synthesis_evaluation(
        artifact_paths=[ARTIFACT_PATH],
        output_dir=tmp_path / "runs",
        validation_report_dir=tmp_path / "reports",
    )
    report_path = tmp_path / "batch_report.md"

    written_path = write_batch_synthesis_report(
        batch_result=batch_result,
        output_path=report_path,
    )

    assert written_path == report_path
    assert report_path.exists()
    assert "LLM Synthesis Batch Evaluation" in report_path.read_text()
