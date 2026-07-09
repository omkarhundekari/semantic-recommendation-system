import json
from pathlib import Path

from planning.shadow_reviewer_report import (
    build_shadow_reviewer_report,
    render_shadow_reviewer_report,
    write_shadow_reviewer_report,
)


def test_shadow_reviewer_report_uses_latest_reviewed_artifacts():
    report = build_shadow_reviewer_report()

    assert report["reviewed_fixtures"] == 5
    assert report["unreviewed_fixtures"] == 5
    assert report["total_review_records"] == 7
    assert report["data_sufficiency_warning"]

    assert report["outcome_distribution"] == {
        "both_weak/exploratory": 1,
        "openai/limited": 1,
        "openai/standard": 3,
    }

    adversarial_status = next(
        row
        for row in report["fixture_review_status"]
        if row["fixture_id"]
        == "adversarial_cloud_incident_health_near_miss"
    )

    assert adversarial_status["artifact_id"] == (
        "414ef0690cd24119b6fd22477fae38b4"
    )
    assert adversarial_status["has_quality_warnings"] is True
    assert adversarial_status["has_suspicious_relevance"] is True


def test_shadow_reviewer_report_summarizes_warning_and_relevance_trace():
    report = build_shadow_reviewer_report()

    warnings = report["quality_warning_summary"]
    assert len(warnings) == 1
    assert warnings[0]["warning_code"] == (
        "adjacent_context_only_candidate"
    )
    assert warnings[0]["candidate_titles"] == [
        "Health Event Incident Correlator"
    ]

    suspicious = [
        trace
        for trace in report["relevance_trace_summary"]
        if trace["was_flagged"]
    ]

    assert len(suspicious) == 1
    assert suspicious[0]["candidate_title"] == (
        "Health Event Incident Correlator"
    )
    assert suspicious[0]["source_id"] == "paper-health-events"
    assert suspicious[0]["relevance_status"] == "adjacent_context_only"


def test_shadow_reviewer_report_markdown_contains_key_sections():
    report = build_shadow_reviewer_report()
    markdown = render_shadow_reviewer_report(report)

    assert "# Shadow Reviewer Report" in markdown
    assert "## Data Sufficiency Warning" in markdown
    assert "## Outcome Distribution" in markdown
    assert "## Quality Warnings Needing Attention" in markdown
    assert "## Suspicious Candidate-to-Source Relevance Traces" in markdown
    assert "adjacent_context_only_candidate" in markdown
    assert "Health Event Incident Correlator" in markdown
    assert "Minimum recommended fixture count before calibration: 15" in markdown


def test_shadow_reviewer_report_writes_markdown_and_json(tmp_path):
    report = build_shadow_reviewer_report()
    paths = write_shadow_reviewer_report(report, tmp_path)

    assert paths["markdown_path"].exists()
    assert paths["json_path"].exists()

    payload = json.loads(paths["json_path"].read_text())
    assert payload["reviewed_fixtures"] == 5
