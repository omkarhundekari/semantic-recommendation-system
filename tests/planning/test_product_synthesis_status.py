from types import SimpleNamespace

from planning.product_synthesis_status import build_synthesis_summary


def test_build_synthesis_summary_reports_valid_preview():
    preview_validation = SimpleNamespace(
        is_valid=True,
        invented_source_ids=(),
        direction_grounding_traces=(
            {"is_grounded": True},
            {"is_grounded": True},
            {"is_grounded": True},
        ),
    )

    summary = build_synthesis_summary(
        routing_decision=SimpleNamespace(
            should_route=True,
            reason="routing_approved",
        ),
        token_estimate=SimpleNamespace(estimated_tokens=2500),
        evidence_cards=[object(), object()],
        preview_validation=preview_validation,
    )

    assert summary == {
        "status": "preview_valid",
        "source": "deterministic_fallback_preview",
        "can_run_llm": True,
        "routing_reason": "routing_approved",
        "card_count": 2,
        "validated": True,
        "grounded_direction_count": 3,
        "invented_source_count": 0,
        "estimated_tokens": 2500,
    }


def test_build_synthesis_summary_reports_invalid_preview():
    preview_validation = SimpleNamespace(
        is_valid=False,
        invented_source_ids=("invented-source",),
        direction_grounding_traces=(
            {"is_grounded": False},
            {"is_grounded": False},
            {"is_grounded": False},
        ),
    )

    summary = build_synthesis_summary(
        routing_decision=SimpleNamespace(
            should_route=False,
            reason="no_query_aligned_evidence",
        ),
        token_estimate=SimpleNamespace(estimated_tokens=1200),
        evidence_cards=[object()],
        preview_validation=preview_validation,
    )

    assert summary["status"] == "preview_invalid"
    assert summary["can_run_llm"] is False
    assert summary["routing_reason"] == "no_query_aligned_evidence"
    assert summary["validated"] is False
    assert summary["grounded_direction_count"] == 0
    assert summary["invented_source_count"] == 1


def test_build_project_intelligence_synthesis_status_returns_valid_preview_contract():
    from planning.product_synthesis_status import (
        build_project_intelligence_synthesis_status,
    )

    evidence_items = [
        {
            "title": "Knowledge Graph-extended Retrieval Augmented Generation for Question Answering",
            "source_type": "research_paper",
            "source_id": "arxiv:2504.08893",
            "support_scope": "direct",
            "relevance_signal": "plausible",
            "summary": (
                "Retrieval augmented generation for question answering using "
                "knowledge graph enhanced retrieval."
            ),
        },
        {
            "title": "infiniflow/ragflow",
            "source_type": "github_repository",
            "source_id": "https://github.com/infiniflow/ragflow",
            "support_scope": "direct",
            "relevance_signal": "plausible",
            "summary": (
                "Open-source RAG engine for retrieval augmented generation."
            ),
        },
    ]

    status = build_project_intelligence_synthesis_status(
        query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "target_roles": ["ML Engineer"],
            "preferred_stack": ["Python"],
        },
        evidence_items=evidence_items,
    )

    assert status["available"] is False
    assert status["reason"] == (
        "live_synthesis_execution_not_enabled_for_project_intelligence"
    )
    assert status["safe_inspection_endpoint"] == "/v1/synthesis-demo"
    assert status["current_planning_source"] == (
        "deterministic_product_pipeline"
    )

    summary = status["synthesis_summary"]
    assert summary["status"] == "preview_valid"
    assert summary["source"] == "deterministic_fallback_preview"
    assert summary["validated"] is True
    assert summary["grounded_direction_count"] == 3
    assert summary["invented_source_count"] == 0
    assert summary["estimated_tokens"] > 0

    assert status["live_evidence_cards"]["card_count"] == 2
    assert status["routing_preview"]["mode"] == "deep"
    assert status["token_estimate"]["estimated_tokens"] > 0

    preview = status["live_final_synthesis_preview"]
    assert preview["source"] == "deterministic_fallback_preview"
    assert preview["fallback_used"] is True
    assert len(preview["parsed_response"]["project_directions"]) == 3

    validation = status["live_final_synthesis_preview_validation"]
    assert validation["is_valid"] is True
    assert validation["invented_source_ids"] == ()
    assert validation["failure_categories"] == ()

    assert status["safety_pipeline"] == {
        "raw_output_validation": True,
        "deterministic_fallback": True,
        "final_synthesis_validation": True,
    }
