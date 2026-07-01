from planning.evidence_brief import build_evidence_brief


def test_brief_preserves_source_provenance_and_retrieval_signals():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Service Observability Through Event Correlation",
                "abstract": (
                    "This work studies event correlation for service "
                    "observability and incident investigation."
                ),
                "category": "cs.SE",
                "url": "https://example.com/paper-1",
                "retrieval_rank": 1,
                "semantic_score": 0.84,
                "rerank_score": 5.7,
            },
            {
                "repository_id": "repo-1",
                "source_type": "github_repository",
                "title": "Incident Investigation Toolkit",
                "readme_excerpt": (
                    "Correlate service events, health checks, and "
                    "observability signals during incident response."
                ),
                "retrieval_rank": 2,
                "rrf_score": 0.031,
            },
        ],
        user_query="Build a service incident investigation project.",
    )

    assert brief.query == "Build a service incident investigation project."
    assert brief.source_counts == {
        "research_paper": 1,
        "github_repository": 1,
    }
    assert len(brief.sources) == 2

    paper = brief.sources[0]
    assert paper.source_id == "paper-1"
    assert paper.source_type == "research_paper"
    assert paper.retrieval_rank == 1
    assert paper.retrieval_signals["semantic_score"] == 0.84
    assert paper.retrieval_signals["rerank_score"] == 5.7


def test_brief_derives_recurring_concepts_from_evidence_not_domain_profiles():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "source_type": "research_paper",
                "title": "Observability for Distributed Services",
                "abstract": (
                    "Observability improves incident response through "
                    "event correlation and service telemetry."
                ),
            },
            {
                "source_type": "github_repository",
                "title": "Event Correlation Platform",
                "readme_excerpt": (
                    "Use observability events and service telemetry "
                    "to investigate incidents."
                ),
            },
        ],
        user_query="Build an operational investigation tool.",
    )

    assert "observability" in brief.recurring_concepts
    assert "service" in brief.recurring_concepts


def test_brief_reports_limited_coverage_without_inventing_support():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "source_type": "project_pattern",
                "title": "Small Workflow Example",
            }
        ],
        user_query="Build a useful project.",
    )

    assert len(brief.sources) == 1
    assert any(
        "Only one evidence source" in warning
        for warning in brief.coverage_warnings
    )
    assert any(
        "No research-paper evidence" in warning
        for warning in brief.coverage_warnings
    )


def test_empty_evidence_produces_an_honest_empty_brief():
    brief = build_evidence_brief(
        evidence_items=[],
        user_query="Build a project.",
    )

    assert brief.sources == []
    assert brief.source_counts == {}
    assert brief.recurring_concepts == []
    assert brief.coverage_warnings == [
        "No usable evidence sources were available."
    ]


def test_brief_preserves_curation_scope_and_retention_reason():
    brief = build_evidence_brief(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Focused Retrieval Evidence",
                "abstract": "Retrieval improves grounded answers.",
                "support_scope": "adjacent_planning",
                "retention_reason": (
                    "Retained as adjacent planning evidence."
                ),
            }
        ],
        user_query="Build a retrieval project.",
    )

    source = brief.sources[0]

    assert source.support_scope == "adjacent_planning"
    assert source.retention_reason == (
        "Retained as adjacent planning evidence."
    )
