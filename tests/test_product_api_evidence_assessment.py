from product_api import build_research_evidence_assessment


def test_builds_api_assessment_from_focused_research_results():
    evidence_payload = {
        "research_results": [
            {
                "document_id": "arxiv:1111.11111",
                "title": "Retrieval-Augmented Generation for Question Answering",
                "abstract": (
                    "We improve retrieval augmented generation for "
                    "question answering with a retrieval method."
                ),
                "category": "cs.IR",
                "retrieval_rank": 1,
            },
            {
                "document_id": "arxiv:2222.22222",
                "title": "RAG Evaluation for Question Answering",
                "abstract": (
                    "We evaluate retrieval augmented generation systems "
                    "for question answering."
                ),
                "category": "cs.IR",
                "retrieval_rank": 2,
            },
            {
                "document_id": "arxiv:3333.33333",
                "title": "Practical RAG Applications",
                "abstract": (
                    "We study retrieval augmented generation applications "
                    "for question answering."
                ),
                "category": "cs.IR",
                "retrieval_rank": 3,
            },
        ]
    }

    result = build_research_evidence_assessment(
        evidence_payload,
        query="retrieval augmented generation for question answering",
    )

    assert result["confidence"]["level"] == "strong"
    assert result["evidence"]["alignment_summary"]["direct"] == 3


def test_returns_none_when_no_research_results_exist():
    assert build_research_evidence_assessment(
        {"research_results": []},
        query="cloud cost optimization",
    ) is None


def test_response_schema_accepts_optional_research_evidence_assessment():
    from schemas.product_models import ProjectIntelligenceResponse

    response = ProjectIntelligenceResponse(
        status="ready",
        query="rag project",
        goal_summary="rag project",
        research_evidence_assessment={
            "confidence": {
                "level": "strong",
            },
        },
    )

    assert response.research_evidence_assessment["confidence"]["level"] == "strong"
