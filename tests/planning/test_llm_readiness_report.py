import json
from pathlib import Path

from planning.llm_readiness_report import (
    build_llm_readiness_report_from_artifact,
    render_llm_readiness_report_markdown,
    write_llm_readiness_report,
)
from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    INTERVIEW_MODE,
    DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE,
    NO_QUERY_ALIGNED_EVIDENCE,
    ROUTING_APPROVED,
    SessionBudgetState,
)


def _load_artifact(relative_path):
    return json.loads(Path(relative_path).read_text())


def _budget():
    return SessionBudgetState(
        calls_remaining=5,
        tokens_remaining=10_000,
        budget_available=True,
    )


def test_llm_readiness_reports_fast_deep_and_interview_modes_for_strong_fixture():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    report = build_llm_readiness_report_from_artifact(
        artifact,
        session_budget=_budget(),
    )
    reports_by_mode = {
        mode_report.mode: mode_report
        for mode_report in report.mode_reports
    }

    assert report.fixture_id == "deterministic_template_risk"
    assert report.evidence_card_count == 3
    assert report.evidence_confidence_counts == {"Strong": 3}
    assert report.grounding_warning_counts == {"none": 3}
    assert report.relevance_signal_counts == {"plausible": 3}

    assert reports_by_mode[
        FAST_MODE
    ].routing_decision.reason == DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE
    assert not reports_by_mode[FAST_MODE].routing_decision.should_route

    assert reports_by_mode[
        DEEP_MODE
    ].routing_decision.reason == ROUTING_APPROVED
    assert reports_by_mode[DEEP_MODE].routing_decision.should_route

    assert reports_by_mode[
        INTERVIEW_MODE
    ].routing_decision.reason == ROUTING_APPROVED
    assert reports_by_mode[INTERVIEW_MODE].routing_decision.should_route

    assert reports_by_mode[DEEP_MODE].token_estimate.estimated_tokens > 0
    assert "evidence_cards" in reports_by_mode[
        DEEP_MODE
    ].token_estimate.largest_sections


def test_llm_readiness_blocks_adjacent_only_exploratory_fixture():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/ambiguous_ai_student_project/"
        "d123d89ceb2742a494f3c6f76a797f09.json"
    )

    report = build_llm_readiness_report_from_artifact(
        artifact,
        session_budget=_budget(),
    )

    assert report.evidence_confidence_counts == {"Exploratory": 3}
    assert report.grounding_warning_counts == {
        "adjacent_context_only": 3,
    }
    assert report.relevance_signal_counts == {"weak": 3}

    for mode_report in report.mode_reports:
        assert not mode_report.routing_decision.should_route
        assert mode_report.routing_decision.reason == NO_QUERY_ALIGNED_EVIDENCE
        assert mode_report.token_estimate.estimated_tokens > 0


def test_llm_readiness_allows_limited_mixed_evidence_in_deep_mode():
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/incident_investigation_broad/"
        "f737ba1de33a41fcab8ff5663795ce5f.json"
    )

    report = build_llm_readiness_report_from_artifact(
        artifact,
        session_budget=_budget(),
    )
    reports_by_mode = {
        mode_report.mode: mode_report
        for mode_report in report.mode_reports
    }

    assert report.evidence_confidence_counts == {
        "Exploratory": 2,
        "Limited": 1,
    }
    assert report.grounding_warning_counts == {
        "adjacent_context_only": 2,
        "none": 1,
    }
    assert reports_by_mode[DEEP_MODE].routing_decision.should_route
    assert reports_by_mode[DEEP_MODE].routing_decision.reason == ROUTING_APPROVED
    assert reports_by_mode[
        DEEP_MODE
    ].routing_decision.evidence_confidence == "Limited"


def test_llm_readiness_markdown_and_json_do_not_leak_review_oracles(tmp_path):
    artifact = _load_artifact(
        "data/manual_fixture_artifacts/deterministic_template_risk/"
        "1bc94b0f56984302922f13d42dcb2a2e.json"
    )

    report = build_llm_readiness_report_from_artifact(
        artifact,
        session_budget=_budget(),
    )
    markdown = render_llm_readiness_report_markdown(report)

    assert "# LLM Readiness Report: deterministic_template_risk" in markdown
    assert "## Mode Routing Summary" in markdown
    assert "`routing_approved`" in markdown
    assert "expected_overall_preference" not in markdown
    assert "manual_review" not in markdown
    assert "oracle" not in markdown

    paths = write_llm_readiness_report(report, tmp_path)

    payload = json.loads(paths["json_path"].read_text())
    serialized = json.dumps(payload)

    assert payload["fixture_id"] == "deterministic_template_risk"
    assert payload["evidence_card_count"] == 3
    assert "mode_reports" in payload
    assert "expected_overall_preference" not in serialized
    assert "manual_review" not in serialized
    assert "oracle" not in serialized
