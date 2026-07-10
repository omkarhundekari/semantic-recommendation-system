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
