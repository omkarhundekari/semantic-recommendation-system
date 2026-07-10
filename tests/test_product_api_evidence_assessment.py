from product_api import (
    build_research_evidence_assessment,
    generate_project_intelligence,
)
from schemas.product_models import ProjectIntelligenceRequest


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
        resolved_planning_domain="rag_llm",
    )

    assert response.research_evidence_assessment["confidence"]["level"] == "strong"
    assert response.resolved_planning_domain == "rag_llm"


def test_api_assessment_uses_registered_required_anchors():
    evidence_payload = {
        "research_results": [
            {
                "document_id": "arxiv:4444.44444",
                "title": "Retrieval-Augmented Generation for Question Answering",
                "abstract": (
                    "We improve retrieval augmented generation for "
                    "question answering with a retrieval method."
                ),
                "category": "cs.IR",
                "retrieval_rank": 1,
            }
        ]
    }

    result = build_research_evidence_assessment(
        evidence_payload,
        query=(
            "Build a retrieval augmented generation project "
            "for question answering"
        ),
    )

    assert result["required_anchor_terms"] == [
        "retrieval augmented generation",
        "question answering",
    ]

def test_ready_api_response_exposes_resolved_rag_planning_domain():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    assert response.status == "ready"
    assert response.inferred_focus == "ai_ml"
    assert response.resolved_planning_domain == "rag_llm"

    assert len(response.directions) == 3
    assert all(
        direction.decision_trace is not None
        for direction in response.directions
    )
    assert all(
        direction.decision_trace.planning_domain == "rag_llm"
        for direction in response.directions
    )

    assert response.product_plan_readiness is not None
    assert response.product_plan_readiness["status"] in {
        "ready",
        "needs_review",
        "blocked",
    }
    assert response.product_plan_readiness["signals"]["direction_count"] == 3
    assert response.product_plan_readiness["signals"][
        "portfolio_difficulties"
    ] == ["Easy", "Medium", "Hard"]


def test_ready_api_response_exposes_synthesis_status_without_raw_llm_output():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    assert response.status == "ready"
    assert response.synthesis_status is not None
    assert response.synthesis_status.available is False
    assert (
        response.synthesis_status.safe_inspection_endpoint
        == "/v1/synthesis-demo"
    )
    assert (
        response.synthesis_status.current_planning_source
        == "deterministic_product_pipeline"
    )
    assert response.synthesis_status.reason == (
        "live_synthesis_execution_not_enabled_for_project_intelligence"
    )

    summary = response.synthesis_status.synthesis_summary
    assert summary.status == "preview_valid"
    assert summary.source == "deterministic_fallback_preview"
    assert isinstance(summary.can_run_llm, bool)
    assert summary.routing_reason
    assert summary.card_count > 0
    assert summary.validated is True
    assert summary.grounded_direction_count == 3
    assert summary.invented_source_count == 0
    assert summary.estimated_tokens > 0

    live_cards = response.synthesis_status.live_evidence_cards
    assert live_cards["card_count"] > 0
    assert live_cards["query_aligned_card_count"] >= 0
    assert {
        "strong_count",
        "limited_count",
        "exploratory_count",
        "weak_card_count",
        "suspicious_card_count",
    }.issubset(live_cards)

    routing_preview = response.synthesis_status.routing_preview
    assert "should_route" in routing_preview
    assert "reason" in routing_preview
    assert routing_preview["mode"] == "deep"

    token_estimate = response.synthesis_status.token_estimate
    assert token_estimate["estimated_tokens"] > 0
    assert "evidence_cards" in token_estimate["section_token_estimates"]

    preview = response.synthesis_status.live_final_synthesis_preview
    assert preview["source"] == "deterministic_fallback_preview"
    assert preview["fallback_used"] is True

    parsed_preview = preview["parsed_response"]
    assert parsed_preview["synthesis_source"] == (
        "deterministic_fallback_preview"
    )
    assert len(parsed_preview["project_directions"]) == 3
    assert all(
        direction["source_ids"]
        for direction in parsed_preview["project_directions"]
    )

    preview_validation = (
        response.synthesis_status.live_final_synthesis_preview_validation
    )
    assert preview_validation["is_valid"] is True
    assert preview_validation["output_path"] == (
        "live_final_synthesis_preview"
    )
    assert preview_validation["invented_source_ids"] == ()
    assert preview_validation["failure_categories"] == ()
    assert all(
        trace["is_grounded"]
        for trace in preview_validation["direction_grounding_traces"]
    )

    assert response.synthesis_status.safety_pipeline == {
        "raw_output_validation": True,
        "deterministic_fallback": True,
        "final_synthesis_validation": True,
    }
