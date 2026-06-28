from planning.candidate_models import CandidateGenerationRequest
from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.planning_orchestrator import plan_candidates


def make_brief():
    return EvidenceBrief(
        query="Build a platform-engineering investigation project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation for Incident Response",
                excerpt=(
                    "Event correlation improves incident investigation "
                    "and service observability workflows."
                ),
            ),
            EvidenceSource(
                source_id="repo-1",
                source_type="github_repository",
                title="Deployment Timeline Toolkit",
                excerpt=(
                    "Build investigation timelines from deployment events "
                    "and service health signals."
                ),
            ),
        ],
    )


def candidate(
    title,
    source_ids,
    workflow,
    mvp_scope,
):
    return {
        "title": title,
        "problem_statement": (
            "Operational evidence is fragmented during incidents."
        ),
        "target_user": "Platform engineers",
        "core_workflow": workflow,
        "mvp_scope": mvp_scope,
        "success_metrics": [
            "Time to identify related operational events.",
        ],
        "evidence_relationship": (
            "Uses evidence-supported incident investigation patterns."
        ),
        "source_ids": source_ids,
        "assumptions": [
            "The prototype uses synthetic operational records."
        ],
        "suggested_stack": ["Python", "FastAPI"],
    }


def test_orchestrator_validates_ranks_and_selects_diverse_candidates():
    provider = MockCandidateGenerationProvider(
        response={
            "candidates": [
                candidate(
                    "Incident Correlation Workbench",
                    ["paper-1", "repo-1"],
                    [
                        "Ingest operational events.",
                        "Correlate related signals.",
                    ],
                    [
                        "Load sample events.",
                        "Correlate related records.",
                        "Show an investigation timeline.",
                    ],
                ),
                candidate(
                    "Incident Event Correlation Dashboard",
                    ["paper-1"],
                    [
                        "Ingest incident events.",
                        "Correlate related service signals.",
                    ],
                    [
                        "Load incident records.",
                        "Correlate related events.",
                        "Render a correlation dashboard.",
                    ],
                ),
                candidate(
                    "Deployment Change Investigation Timeline",
                    ["repo-1"],
                    [
                        "Ingest deployment changes.",
                        "Compare health signals after releases.",
                    ],
                    [
                        "Load deployment events.",
                        "Compare deployment and health records.",
                        "Render a release investigation timeline.",
                    ],
                ),
            ]
        }
    )

    outcome = plan_candidates(
        brief=make_brief(),
        request=CandidateGenerationRequest(
            user_goal=(
                "Build a platform-engineering investigation project."
            ),
            time_available="3 weeks",
            target_roles=["Platform Engineer"],
            preferred_stack=["Python", "FastAPI"],
        ),
        provider=provider,
        max_candidates=2,
    )

    selected_titles = [
        ranked.candidate.title
        for ranked in outcome.selected_candidates
    ]

    assert outcome.provider_called is True
    assert len(outcome.generated_candidates) == 3
    assert len(outcome.valid_candidates) == 3
    assert len(outcome.ranked_candidates) == 3
    assert len(outcome.selected_candidates) == 2
    assert "Incident Correlation Workbench" in selected_titles
    assert "Deployment Change Investigation Timeline" in selected_titles
    assert "Incident Event Correlation Dashboard" not in selected_titles
    assert outcome.diagnostics()["selected_candidate_count"] == 2


def test_orchestrator_returns_no_selected_candidates_when_all_fail_validation():
    provider = MockCandidateGenerationProvider(
        response={
            "candidates": [
                candidate(
                    "Unsupported Candidate",
                    ["invented-source"],
                    ["Read unsupported evidence."],
                    [
                        "Load records.",
                        "Process records.",
                        "Show output.",
                    ],
                )
            ]
        }
    )

    outcome = plan_candidates(
        brief=make_brief(),
        request=CandidateGenerationRequest(
            user_goal="Build a platform project."
        ),
        provider=provider,
    )

    assert outcome.selected_candidates == []
    assert outcome.valid_candidates == []
    assert outcome.validation_errors
