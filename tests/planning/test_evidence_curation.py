from planning.evidence_curation import curate_evidence


def test_curator_drops_unrelated_automl_pattern_for_rag_qa_query():
    result = curate_evidence(
        evidence_items=[
            {
                "source_type": "project_pattern",
                "title": "AutoML Experiment Recommendation Assistant",
                "tags": "machine learning, experiments",
            },
            {
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
                "source_type": "github_repository",
                "title": "HKUDS/LightRAG",
                "readme_excerpt": (
                    "LightRAG supports retrieval augmented generation "
                    "workflows."
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
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering for ML engineer roles in 3 weeks"
        ),
    )

    retained_titles = [
        entry.item["title"]
        for entry in result.retained
    ]
    dropped_titles = [
        entry.item["title"]
        for entry in result.dropped
    ]

    assert result.required_anchor_terms == [
        "retrieval augmented generation",
        "question answering",
    ]
    assert "AutoML Experiment Recommendation Assistant" in dropped_titles
    assert (
        "Knowledge Graph-extended Retrieval Augmented "
        "Generation for Question Answering"
    ) in retained_titles
    assert "Citation Coverage Checker for LLM Answers" in retained_titles


def test_curator_retains_adjacent_source_with_meaningful_query_overlap():
    result = curate_evidence(
        evidence_items=[
            {
                "source_type": "research_paper",
                "title": (
                    "Retrieval Augmented Generation-Based Incident "
                    "Resolution Recommendation System"
                ),
                "abstract": (
                    "A retrieval augmented generation workflow for "
                    "incident resolution."
                ),
            }
        ],
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
    )

    assert len(result.retained) == 1
    assert "retrieval augmented generation" in (
        result.retained[0].matched_anchor_terms
    )


def test_curator_keeps_generic_queries_usable_without_registered_anchors():
    result = curate_evidence(
        evidence_items=[
            {
                "source_type": "github_repository",
                "title": "Cloud Cost Optimization Toolkit",
                "readme_excerpt": (
                    "Analyze cloud cost and resource optimization."
                ),
            },
            {
                "source_type": "project_pattern",
                "title": "Recipe Discovery App",
                "tags": "food, mobile",
            },
        ],
        user_query="Build a cloud cost optimization project.",
    )

    retained_titles = [
        entry.item["title"]
        for entry in result.retained
    ]

    assert result.required_anchor_terms == []
    assert "Cloud Cost Optimization Toolkit" in retained_titles
    assert "Recipe Discovery App" not in retained_titles


def test_curator_preserves_adjacent_ranked_evidence_for_broad_queries():
    result = curate_evidence(
        evidence_items=[
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Event Correlation for Incident Investigation",
                "abstract": (
                    "Event correlation improves incident investigation."
                ),
                "retrieval_rank": 1,
            },
            {
                "repository_id": "repo-1",
                "source_type": "github_repository",
                "title": "Incident Timeline Toolkit",
                "readme_excerpt": (
                    "Build timelines from health signals and incident events."
                ),
                "retrieval_rank": 2,
            },
            {
                "source_type": "project_pattern",
                "title": "Platform Engineering Investigation Dashboard",
                "tags": "observability, incident response",
                "retrieval_rank": 3,
            },
        ],
        user_query="Build a platform engineering project in 3 weeks.",
    )

    retained_titles = [
        entry.item["title"]
        for entry in result.retained
    ]

    assert result.required_anchor_terms == []
    assert len(retained_titles) == 3
    assert "Event Correlation for Incident Investigation" in retained_titles
    assert "Incident Timeline Toolkit" in retained_titles
    assert "Platform Engineering Investigation Dashboard" in retained_titles

    assert any(
        "retrieval-ranked adjacent evidence"
        in entry.retention_reason
        for entry in result.retained
    )
