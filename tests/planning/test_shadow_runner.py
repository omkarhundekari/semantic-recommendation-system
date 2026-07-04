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


def test_shadow_runner_curates_unrelated_sources_before_generation():
    report = run_shadow_plan(
        evidence_items=[
            {
                "source_type": "project_pattern",
                "title": "AutoML Experiment Recommendation Assistant",
                "tags": "machine learning, experiments",
            },
            {
                "document_id": "paper-rag",
                "source_type": "research_paper",
                "title": (
                    "Knowledge Graph-extended Retrieval Augmented "
                    "Generation for Question Answering"
                ),
                "abstract": (
                    "Retrieval augmented generation improves "
                    "question answering."
                ),
            },
            {
                "source_type": "project_pattern",
                "title": "Citation Coverage Checker for LLM Answers",
                "tags": (
                    "retrieval augmented generation, citations, "
                    "question answering"
                ),
            },
        ],
        user_goal=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Citation-Aware RAG Evaluation Workbench",
                        "problem_statement": (
                            "RAG answers need inspectable citation coverage."
                        ),
                        "target_user": "ML engineers",
                        "core_workflow": [
                            "Load retrieved context and generated answers.",
                            "Evaluate citation coverage.",
                        ],
                        "mvp_scope": [
                            "Load a small RAG evaluation dataset.",
                            "Calculate citation coverage.",
                            "Show answer-level warnings.",
                        ],
                        "success_metrics": [
                            "Citation coverage across evaluation examples."
                        ],
                        "evidence_relationship": (
                            "Uses the retained RAG and citation evidence."
                        ),
                        "source_ids": [
                            "paper-rag",
                            "Citation Coverage Checker for LLM Answers",
                        ],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
    )

    retained_titles = [
        source["title"]
        for source in report.evidence_brief["sources"]
    ]
    dropped_titles = [
        entry["item"]["title"]
        for entry in report.evidence_curation["dropped"]
    ]

    assert "AutoML Experiment Recommendation Assistant" in dropped_titles
    assert "AutoML Experiment Recommendation Assistant" not in retained_titles
    assert report.comparison["raw_evidence_count"] == 3
    assert report.comparison["curated_evidence_count"] == 2
    assert report.planning_diagnostics["valid_candidate_count"] == 1


def test_shadow_runner_preserves_curation_metadata_in_evidence_brief():
    report = run_shadow_plan(
        evidence_items=[
            {
                "document_id": "paper-rag",
                "source_type": "research_paper",
                "title": "Retrieval Augmented Generation for Question Answering",
                "abstract": (
                    "Retrieval augmented generation supports "
                    "question answering."
                ),
            }
        ],
        user_goal="Build a retrieval augmented generation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Grounded QA Workbench",
                        "problem_statement": "Answers need source support.",
                        "target_user": "ML engineers",
                        "core_workflow": [
                            "Retrieve relevant passages.",
                            "Generate cited answers.",
                        ],
                        "mvp_scope": [
                            "Load sample documents.",
                            "Retrieve relevant passages.",
                            "Return answers with citations.",
                        ],
                        "success_metrics": [
                            "Citation coverage per answer.",
                        ],
                        "evidence_relationship": (
                            "Uses the retained RAG research evidence."
                        ),
                        "source_ids": ["paper-rag"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
    )

    source = report.evidence_brief["sources"][0]

    assert source["support_scope"] == "direct"
    assert "Matched" in source["retention_reason"]


def test_shadow_runner_exposes_phrase_frequency_diagnostics():
    report = run_shadow_plan(
        evidence_items=[
            {
                "source_type": "project_pattern",
                "title": "Flaky Test Detection Dashboard",
                "tags": "flaky-tests,testing,ci-cd,reliability",
            },
            {
                "source_type": "github_repository",
                "title": "Code Review Assistant",
                "readme_excerpt": (
                    "Analyze code changes and improve developer productivity."
                ),
            },
            {
                "source_type": "project_pattern",
                "title": "Commit Change Analytics",
                "tags": "code-changes,developer-tools,repository",
            },
        ],
        user_goal=(
            "Build a developer productivity project that helps engineers "
            "identify flaky tests, connect failures with code changes."
        ),
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={"candidates": []}
        ),
    )

    retained = {
        entry["item"]["title"]: entry
        for entry in report.evidence_curation["retained"]
    }

    flaky = retained["Flaky Test Detection Dashboard"]

    code_review = retained["Code Review Assistant"]

    assert "flaky tests" in flaky["matched_query_phrases"]
    assert flaky["query_phrase_document_frequencies"][
        "flaky tests"
    ] == 1
    assert flaky["query_term_document_frequencies"]["flaky"] == 1
    assert code_review["query_term_document_frequencies"]["code"] == 2
    assert flaky["unique_query_terms"] == ["flaky", "tests"]
    assert flaky["unique_query_phrases"] == ["flaky tests"]
    assert code_review["unique_query_terms"] == ["productivity"]
    assert code_review["unique_query_phrases"] == [
        "developer productivity"
    ]
    assert flaky["curation_pool_size"] == 3


def test_shadow_runner_marks_well_supported_output_ready():
    report = run_shadow_plan(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Incident Correlation Research",
                "abstract": (
                    "Event correlation improves incident investigation "
                    "and observability workflows."
                ),
            },
            {
                "repository_id": "repo-1",
                "source_type": "github_repository",
                "title": "Incident Timeline Toolkit",
                "readme_excerpt": (
                    "Build investigation timelines from incident events "
                    "and deployment signals."
                ),
            },
        ],
        user_goal="Build an incident investigation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Correlation Workbench",
                        "problem_statement": (
                            "Incident signals are difficult to connect."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident signals.",
                            "Correlate related events.",
                        ],
                        "mvp_scope": [
                            "Load sample incident records.",
                            "Link related events.",
                            "Show an investigation timeline.",
                        ],
                        "success_metrics": [
                            "Time required to identify related events.",
                        ],
                        "evidence_relationship": (
                            "Uses the retained incident-correlation "
                            "evidence."
                        ),
                        "source_ids": ["paper-1", "repo-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
    )

    assert report.shadow_readiness["status"] == "ready"
    assert report.shadow_readiness["signals"][
        "curated_evidence_count"
    ] == 2
    assert report.shadow_readiness["signals"][
        "selected_candidate_count"
    ] == 1


def test_shadow_runner_blocks_output_without_valid_candidates():
    report = run_shadow_plan(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Incident Correlation Research",
                "abstract": (
                    "Event correlation improves incident investigation."
                ),
            }
        ],
        user_goal="Build an incident investigation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={"candidates": []}
        ),
    )

    assert report.shadow_readiness["status"] == "blocked"
    assert (
        "No valid candidate directions were produced."
        in report.shadow_readiness["reasons"]
    )
    assert (
        "No ranked candidate directions were selected."
        in report.shadow_readiness["reasons"]
    )


def test_shadow_runner_marks_single_source_output_for_review():
    report = run_shadow_plan(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Event Correlation",
                "abstract": (
                    "Event correlation supports investigation workflows."
                ),
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

    assert report.shadow_readiness["status"] == "needs_review"
    assert (
        "Only one evidence source was available, so cross-source "
        "support is limited."
        in report.shadow_readiness["reasons"]
    )
