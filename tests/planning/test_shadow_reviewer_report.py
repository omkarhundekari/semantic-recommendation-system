import json
from pathlib import Path

from planning.shadow_reviewer_report import (
    build_shadow_reviewer_report,
    render_shadow_reviewer_report,
    write_shadow_reviewer_report,
)


def test_shadow_reviewer_report_uses_latest_reviewed_artifacts():
    report = build_shadow_reviewer_report()

    assert report["reviewed_fixtures"] == 6
    assert report["unreviewed_fixtures"] == 4
    assert report["total_review_records"] == 8
    assert report["review_annotation_count"] == 6
    assert report["latest_review_annotation_count"] == 6
    assert report["data_sufficiency_warning"]

    assert report["outcome_distribution"] == {
        "both_weak/exploratory": 1,
        "openai/limited": 2,
        "openai/standard": 3,
    }
    assert report["oracle_comparison_counts"] == {
        "matched": 5,
        "mismatch": 1,
        "missing_review": 1,
    }
    assert report["reviewer_confidence_counts"] == {"high": 6}
    assert report["both_weak_diagnosis_counts"] == {
        "evidence_sparse": 1,
    }
    assert report["relevance_trace_assessment_counts"] == {
        "traces_match_reviewer_judgment": 6,
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
    assert adversarial_status["reviewer_confidence"] == "high"
    assert adversarial_status["relevance_trace_assessment"] == (
        "traces_match_reviewer_judgment"
    )
    assert adversarial_status["has_quality_warnings"] is True
    assert adversarial_status["has_suspicious_relevance"] is True


def test_shadow_reviewer_report_summarizes_warning_and_relevance_trace():
    report = build_shadow_reviewer_report()

    warnings = report["quality_warning_summary"]
    assert len(warnings) == 2

    warnings_by_fixture = {
        warning["fixture_id"]: warning
        for warning in warnings
    }

    assert warnings_by_fixture[
        "adversarial_cloud_incident_health_near_miss"
    ]["warning_code"] == "adjacent_context_only_candidate"
    assert warnings_by_fixture[
        "adversarial_cloud_incident_health_near_miss"
    ]["candidate_titles"] == [
        "Health Event Incident Correlator"
    ]
    assert warnings_by_fixture[
        "strict_weekend_scope"
    ]["candidate_titles"] == [
        "Simple Remediation Priority Ranker"
    ]

    suspicious = [
        trace
        for trace in report["relevance_trace_summary"]
        if trace["was_flagged"]
    ]

    assert len(suspicious) == 2

    suspicious_by_candidate = {
        trace["candidate_title"]: trace
        for trace in suspicious
    }

    assert suspicious_by_candidate[
        "Health Event Incident Correlator"
    ]["source_id"] == "paper-health-events"
    assert suspicious_by_candidate[
        "Health Event Incident Correlator"
    ]["relevance_status"] == "adjacent_context_only"
    assert suspicious_by_candidate[
        "Simple Remediation Priority Ranker"
    ]["source_id"] == "paper-data-incident-triage"
    assert suspicious_by_candidate[
        "Simple Remediation Priority Ranker"
    ]["relevance_status"] == "adjacent_context_only"


def test_shadow_reviewer_report_markdown_contains_key_sections():
    report = build_shadow_reviewer_report()
    markdown = render_shadow_reviewer_report(report)

    assert "# Shadow Reviewer Report" in markdown
    assert "## Data Sufficiency Warning" in markdown
    assert "## Outcome Distribution" in markdown
    assert "## Oracle Comparison Summary" in markdown
    assert "`matched`: 5" in markdown
    assert "`mismatch`: 1" in markdown
    assert "`missing_review`: 1" in markdown
    assert "## Review Annotation Summary" in markdown
    assert "`high`: 6" in markdown
    assert "`evidence_sparse`: 1" in markdown
    assert "`traces_match_reviewer_judgment`: 6" in markdown
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
    assert payload["reviewed_fixtures"] == 6
    assert payload["review_annotation_count"] == 6
    assert payload["oracle_comparison_counts"] == {
        "matched": 5,
        "mismatch": 1,
        "missing_review": 1,
    }
