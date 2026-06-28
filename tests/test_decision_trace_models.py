import pytest
from pydantic import ValidationError

from schemas.decision_trace_models import (
    DetectedSignal,
    ImplementationReference,
    ProjectDecisionTrace,
    SupportingPaperEvidence,
)


def test_project_decision_trace_accepts_research_and_implementation_support():
    trace = ProjectDecisionTrace(
        idea_id="direction-1",
        idea_title="RAG Evaluation Studio",
        research_support_scope="planning_domain",
        supporting_papers=[
            SupportingPaperEvidence(
                document_id="arxiv:2504.08893",
                title=(
                    "Knowledge Graph-extended Retrieval Augmented "
                    "Generation for Question Answering"
                ),
                category="cs.LG",
                retrieval_rank=1,
                alignment="direct",
                evidence_tags=["method", "limitation", "application"],
                evidence_snippets=["RAG systems can suffer from hallucinations."],
                matched_query_terms=["retrieval", "generation"],
                matched_query_phrases=["retrieval augmented generation"],
                matched_required_anchor_terms=[
                    "retrieval augmented generation",
                    "question answering",
                ],
                alignment_reason="The paper matches required RAG anchors.",
            )
        ],
        evidence_tags=["method", "limitation", "application"],
        detected_signals=[
            DetectedSignal(
                group="methods",
                name="retrieval",
                paper_count=3,
                supporting_document_ids=[
                    "arxiv:2504.08893",
                    "arxiv:2409.13707",
                    "arxiv:2411.02832",
                ],
            )
        ],
        buildable_gap="Make RAG failure modes visible and measurable.",
        confidence_level="strong",
        confidence_reason="Direct RAG evidence is the majority.",
        planning_domain="rag_llm",
        planning_domain_reason=(
            "Registered RAG and question-answering anchors selected "
            "the RAG planning domain."
        ),
        idea_specific_rationale=(
            "Evaluate retrieval quality, grounding, and citation coverage."
        ),
        implementation_references=[
            ImplementationReference(
                title="HKUDS/LightRAG",
                source_type="github_repository",
                architecture_signals=["retrieval_and_search"],
                technology_signals=["Python", "Docker"],
                trusted=True,
            )
        ],
        assumptions=["Use a small reproducible document collection."],
        evidence_gaps=["No deterministic feasibility result exists yet."],
    )

    assert trace.supporting_papers[0].alignment == "direct"
    assert trace.detected_signals[0].name == "retrieval"
    assert trace.feasibility_result is None


def test_project_decision_trace_rejects_unknown_confidence_level():
    with pytest.raises(ValidationError):
        ProjectDecisionTrace(
            idea_id="direction-1",
            idea_title="RAG Evaluation Studio",
            research_support_scope="planning_domain",
            buildable_gap="Make RAG failure modes visible and measurable.",
            confidence_level="high",
            confidence_reason="Unsupported confidence label.",
            planning_domain="rag_llm",
            planning_domain_reason="RAG anchors selected the domain.",
            idea_specific_rationale="Evaluate RAG quality.",
        )
