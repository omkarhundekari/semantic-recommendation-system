from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.shadow_runner import run_shadow_plan


def make_provider_response():
    return {
        "candidates": [
            {
                "title": "Evidence-Aware Incident Investigation Workbench",
                "problem_statement": (
                    "Operational records are difficult to connect during "
                    "service incidents."
                ),
                "target_user": "Platform engineers",
                "core_workflow": [
                    "Load service event records.",
                    "Correlate related incident signals.",
                ],
                "mvp_scope": [
                    "Load a small operational-event dataset.",
                    "Link records using simple correlation rules.",
                    "Render an investigation timeline.",
                ],
                "success_metrics": [
                    "Time required to identify related incident events.",
                ],
                "evidence_relationship": (
                    "Uses the retrieved paper and repository as evidence "
                    "for correlation and investigation workflows."
                ),
                "source_ids": [
                    "arxiv:1111.11111",
                    "repo-incident-toolkit",
                ],
                "assumptions": [
                    "The MVP uses synthetic operational records."
                ],
                "suggested_stack": ["Python", "FastAPI"],
            },
            {
                "title": "Deployment Health Change Explorer",
                "problem_statement": (
                    "Teams struggle to inspect whether deployments "
                    "coincide with service-health changes."
                ),
                "target_user": "Platform engineers",
                "core_workflow": [
                    "Load deployment records.",
                    "Compare releases with service-health signals.",
                ],
                "mvp_scope": [
                    "Load deployment and health records.",
                    "Match time windows around releases.",
                    "Show a release investigation view.",
                ],
                "success_metrics": [
                    "Number of release-health correlations surfaced.",
                ],
                "evidence_relationship": (
                    "Uses the repository evidence for timeline-based "
                    "investigation workflows."
                ),
                "source_ids": ["repo-incident-toolkit"],
                "assumptions": [
                    "The MVP uses a fixed sample release history."
                ],
                "suggested_stack": ["Python", "FastAPI"],
            },
        ]
    }


def test_shadow_runner_uses_realistic_merged_evidence_shape():
    evidence_items = [
        {
            "document_id": "arxiv:1111.11111",
            "source_type": "research_paper",
            "title": "Event Correlation for Incident Investigation",
            "abstract": (
                "Event correlation improves service incident investigation "
                "and operational observability."
            ),
            "category": "cs.SE",
            "url": "https://arxiv.org/abs/1111.11111",
            "retrieval_rank": 1,
            "rrf_score": 0.042,
            "retrieval_phase": "focused",
        },
        {
            "repository_id": "repo-incident-toolkit",
            "source_type": "github_repository",
            "title": "Incident Timeline Toolkit",
            "readme_excerpt": (
                "Build deployment timelines from health signals and "
                "incident events."
            ),
            "architecture_signals": (
                "event_ingestion, timeline_visualization"
            ),
            "technology_signals": "Python, FastAPI",
            "url": "https://github.com/example/incident-toolkit",
            "retrieval_rank": 2,
            "retrieval_phase": "focused",
        },
        {
            "source_type": "project_pattern",
            "title": "Platform Engineering Investigation Dashboard",
            "tags": "observability, incident response",
            "skills": "Python, APIs",
            "target_roles": "Platform Engineer",
            "selection_reason": (
                "Relevant pattern for operational investigation workflows."
            ),
            "retrieval_rank": 3,
            "retrieval_phase": "focused",
        },
    ]

    legacy_ideas = [
        {"project_title": "Legacy Incident Dashboard"},
        {"project_title": "Legacy Deployment Analyzer"},
    ]

    report = run_shadow_plan(
        evidence_items=evidence_items,
        user_goal="Build a platform engineering project in 3 weeks.",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
            "preferred_stack": ["Python", "FastAPI"],
        },
        provider=MockCandidateGenerationProvider(
            response=make_provider_response()
        ),
        legacy_ideas=legacy_ideas,
        max_candidates=2,
    )

    assert report.comparison["provider_called"] is True
    assert report.comparison["legacy_direction_count"] == 2
    assert report.comparison["v2_generated_candidate_count"] == 2
    assert report.comparison["v2_valid_candidate_count"] == 2
    assert report.comparison["v2_selected_candidate_count"] == 2

    assert report.evidence_brief["source_counts"] == {
        "research_paper": 1,
        "github_repository": 1,
        "project_pattern": 1,
    }

    assert report.selected_titles == [
        "Evidence-Aware Incident Investigation Workbench",
        "Deployment Health Change Explorer",
    ]

    assert report.legacy_titles == [
        "Legacy Incident Dashboard",
        "Legacy Deployment Analyzer",
    ]


def test_shadow_runner_includes_ranked_selected_candidate_details():
    report = run_shadow_plan(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Event Correlation",
                "abstract": "Event correlation supports investigation.",
            }
        ],
        user_goal="Build an investigation tool.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Correlation Investigation Workbench",
                        "problem_statement": "Signals are disconnected.",
                        "target_user": "Engineers",
                        "core_workflow": [
                            "Load signals.",
                            "Correlate related records.",
                        ],
                        "mvp_scope": [
                            "Load sample records.",
                            "Correlate signals.",
                            "Show a timeline.",
                        ],
                        "success_metrics": [
                            "Related-record discovery time.",
                        ],
                        "evidence_relationship": (
                            "Uses the retrieved correlation evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
    )

    assert len(report.selected_candidates) == 1
    assert report.selected_candidates[0]["title"] == (
        "Correlation Investigation Workbench"
    )
    assert "ranking" in report.selected_candidates[0]
