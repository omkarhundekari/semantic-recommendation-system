from planning.candidate_models import CandidateDirection
from planning.candidate_source_relevance import (
    assess_candidate_source_relevance,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def _candidate(title, problem, source_ids):
    return CandidateDirection(
        title=title,
        problem_statement=problem,
        target_user="Platform engineers",
        core_workflow=[
            "Load deployment and service-health events.",
            "Correlate operational incident evidence.",
        ],
        mvp_scope=["Load sample records.", "Show an incident timeline."],
        success_metrics=["Time to investigate incidents."],
        evidence_relationship="Uses cited evidence.",
        source_ids=source_ids,
    )


def _brief():
    return EvidenceBrief(
        query=(
            "Build a cloud incident investigation project that correlates "
            "deployment changes with service-health events."
        ),
        sources=[
            EvidenceSource(
                source_id="paper-cloud",
                source_type="research_paper",
                title="Event Correlation for Cloud Incident Investigation",
                excerpt=(
                    "Correlating deployment changes, service health, and "
                    "operational telemetry supports cloud incident investigation."
                ),
                support_scope="direct",
            ),
            EvidenceSource(
                source_id="paper-health",
                source_type="research_paper",
                title="Continuous Health Event Retrieval",
                excerpt=(
                    "Retrieve and summarize event sequences from continuous "
                    "personal health data."
                ),
                support_scope="adjacent_planning",
            ),
        ],
    )


def test_direct_cloud_source_has_lexical_support_trace():
    traces = assess_candidate_source_relevance(
        candidate=_candidate(
            "Deployment-to-Incident Correlation Workbench",
            (
                "Platform engineers need to correlate deployment changes "
                "with service-health degradation during incidents."
            ),
            ["paper-cloud"],
        ),
        brief=_brief(),
        user_goal=_brief().query,
    )

    assert len(traces) == 1
    assert traces[0].relevance_status == "lexically_supported"
    assert "incident" in traces[0].candidate_source_shared_terms


def test_adjacent_health_source_is_flagged_as_context_only():
    traces = assess_candidate_source_relevance(
        candidate=_candidate(
            "Health Event Incident Correlator",
            (
                "Teams need to correlate health events during operational "
                "incidents."
            ),
            ["paper-health"],
        ),
        brief=_brief(),
        user_goal=_brief().query,
    )

    assert len(traces) == 1
    assert traces[0].relevance_status == "adjacent_context_only"
    assert traces[0].support_scope == "adjacent_planning"
    assert "core grounding" in traces[0].relevance_reason


def test_unknown_source_id_is_explicitly_traced():
    traces = assess_candidate_source_relevance(
        candidate=_candidate(
            "Unknown Citation Tool",
            "Investigate operational incidents.",
            ["missing-source"],
        ),
        brief=_brief(),
        user_goal=_brief().query,
    )

    assert traces[0].relevance_status == "invalid_source_id"
