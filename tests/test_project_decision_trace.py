from project_decision_trace import build_project_decision_trace


def build_assessment():
    return {
        "required_anchor_terms": [
            "retrieval augmented generation",
            "question answering",
        ],
        "confidence": {
            "level": "strong",
            "reason": "Direct RAG evidence is the majority.",
        },
        "evidence": {
            "evidence_tags": {
                "method": 6,
                "limitation": 2,
                "application": 5,
            },
            "signals": {
                "methods": {
                    "retrieval": {
                        "paper_count": 2,
                        "document_ids": [
                            "arxiv:2504.08893",
                            "arxiv:2409.13707",
                        ],
                    }
                }
            },
            "alignment_summary": {
                "direct": 2,
                "adjacent": 1,
                "weak": 1,
            },
            "supporting_papers": [
                {
                    "document_id": "arxiv:2504.08893",
                    "title": (
                        "Knowledge Graph-extended Retrieval Augmented "
                        "Generation for Question Answering"
                    ),
                    "category": "cs.LG",
                    "retrieval_rank": 1,
                    "evidence_tags": [
                        "method",
                        "limitation",
                        "application",
                    ],
                    "evidence_snippets": [
                        "RAG systems can suffer from hallucinations."
                    ],
                    "alignment": "direct",
                    "matched_query_terms": ["retrieval", "generation"],
                    "matched_query_phrases": [
                        "retrieval augmented generation"
                    ],
                    "matched_required_anchor_terms": [
                        "retrieval augmented generation",
                        "question answering",
                    ],
                    "reason": "The paper matches required RAG anchors.",
                },
                {
                    "document_id": "arxiv:2409.13707",
                    "title": "Unrelated Adjacent Retrieval Study",
                    "category": "cs.IR",
                    "retrieval_rank": 2,
                    "evidence_tags": ["method"],
                    "evidence_snippets": [],
                    "alignment": "adjacent",
                    "matched_query_terms": ["retrieval"],
                    "matched_query_phrases": [],
                    "matched_required_anchor_terms": [],
                    "reason": "Adjacent retrieval topic.",
                },
            ],
        },
    }


def test_research_paper_trace_keeps_only_its_matching_paper():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": "Inspect RAG pipeline failures.",
        "evidence_focus_statement": (
            "Inspect retrieval quality, answer grounding, and citation coverage."
        ),
        "evidence_title": (
            "Knowledge Graph-extended Retrieval Augmented "
            "Generation for Question Answering"
        ),
        "evidence_source_type": "research_paper",
        "evidence_url": "https://arxiv.org/abs/2504.08893",
        "source_contributions": [
            {
                "title": "HKUDS/LightRAG",
                "source_type": "github_repository",
                "architecture_signals": ["retrieval_and_search"],
                "technology_signals": ["Python", "Docker"],
                "trusted": True,
            }
        ],
    }

    trace = build_project_decision_trace(
        idea=idea,
        idea_id="direction-1",
        assessment=build_assessment(),
        query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
    )

    assert trace.research_support_scope == "idea_specific"
    assert len(trace.supporting_papers) == 1
    assert trace.supporting_papers[0].document_id == "arxiv:2504.08893"
    assert trace.implementation_references == []
    assert trace.primary_inspiration is not None
    assert trace.primary_inspiration.source_type == "research_paper"


def test_project_pattern_trace_uses_mixed_support_without_copying_papers():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": "Inspect RAG pipeline failures.",
        "evidence_focus_statement": "Inspect retrieval and grounding quality.",
        "evidence_title": "AutoML Experiment Recommendation Assistant",
        "evidence_source_type": "project_pattern",
    }

    trace = build_project_decision_trace(
        idea=idea,
        idea_id="direction-2",
        assessment=build_assessment(),
        query="Build a retrieval augmented generation project",
    )

    assert trace.research_support_scope == "mixed"
    assert trace.supporting_papers == []
    assert trace.implementation_references == []
    assert "broader planning domain" in trace.assumptions[0]


def test_github_trace_keeps_only_its_matching_repository_reference():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": "Inspect RAG pipeline failures.",
        "evidence_title": "HKUDS/LightRAG",
        "evidence_source_type": "github_repository",
        "source_contributions": [
            {
                "title": "HKUDS/LightRAG",
                "source_type": "github_repository",
                "architecture_signals": ["retrieval_and_search"],
                "technology_signals": ["Python", "Docker"],
                "trusted": True,
            },
            {
                "title": "Other Repository",
                "source_type": "github_repository",
                "architecture_signals": ["evaluation_and_monitoring"],
                "technology_signals": ["FastAPI"],
                "trusted": False,
            },
        ],
    }

    trace = build_project_decision_trace(
        idea=idea,
        idea_id="direction-3",
        assessment=build_assessment(),
        query="Build a retrieval augmented generation project",
    )

    assert trace.research_support_scope == "mixed"
    assert trace.supporting_papers == []
    assert len(trace.implementation_references) == 1
    assert trace.implementation_references[0].title == "HKUDS/LightRAG"


def test_unknown_source_uses_planning_domain_support():
    idea = {
        "project_title": "Generic RAG Planner",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": "Inspect RAG pipeline failures.",
        "evidence_source_type": "",
    }

    trace = build_project_decision_trace(
        idea=idea,
        idea_id="direction-4",
        assessment=build_assessment(),
        query="Build a retrieval augmented generation project",
    )

    assert trace.research_support_scope == "planning_domain"
    assert trace.supporting_papers == []
    assert "not attributed to one specific paper" in trace.assumptions[0]


def test_research_paper_missing_from_assessment_adds_gap():
    idea = {
        "project_title": "RAG Evaluation Studio",
        "detected_domain": "rag_llm",
        "evidence_buildable_gap": "Inspect RAG pipeline failures.",
        "evidence_title": "Paper Not Present In Assessment",
        "evidence_source_type": "research_paper",
    }

    trace = build_project_decision_trace(
        idea=idea,
        idea_id="direction-5",
        assessment=build_assessment(),
        query="Build a retrieval augmented generation project",
    )

    assert trace.research_support_scope == "idea_specific"
    assert trace.supporting_papers == []
    assert any(
        "not present in the focused assessment evidence" in gap
        for gap in trace.evidence_gaps
    )
