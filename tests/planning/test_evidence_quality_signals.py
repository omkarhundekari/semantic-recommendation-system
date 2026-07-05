import pytest

from planning.evidence_brief import build_evidence_brief
from planning.evidence_curation import curate_evidence
from planning.evidence_quality_signals import (
    EvidenceQualityThresholds,
    assess_evidence_quality_signals,
    build_evidence_quality_metrics,
)


def make_curation_and_brief():
    evidence_items = [
        {
            "document_id": "paper-1",
            "source_type": "research_paper",
            "title": (
                "Retrieval Augmented Generation for Question Answering"
            ),
            "abstract": (
                "Retrieval augmented generation improves question "
                "answering with grounded context."
            ),
        },
        {
            "repository_id": "repo-1",
            "source_type": "github_repository",
            "title": "RAG Evaluation Toolkit",
            "readme_excerpt": (
                "Evaluate retrieval augmented generation answers and "
                "citation coverage."
            ),
        },
        {
            "source_type": "project_pattern",
            "title": "Citation Coverage Dashboard",
            "tags": (
                "retrieval augmented generation, question answering, "
                "citations"
            ),
        },
    ]

    curation = curate_evidence(
        evidence_items=evidence_items,
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
    )

    brief = build_evidence_brief(
        evidence_items=[
            {
                **entry.item,
                "support_scope": entry.support_scope,
                "retention_reason": entry.retention_reason,
            }
            for entry in curation.retained
        ],
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
    )

    return curation, brief


def test_builds_metrics_from_curation_and_final_brief():
    curation, brief = make_curation_and_brief()

    metrics = build_evidence_quality_metrics(curation, brief)

    assert metrics.curation_pool_size == 3
    assert metrics.retained_source_count == 3
    assert metrics.final_brief_source_count == 3
    assert metrics.direct_source_count >= 1
    assert metrics.required_anchor_count == 2
    assert metrics.matched_required_anchor_count == 2
    assert metrics.query_anchor_coverage == 1.0
    assert metrics.source_type_count == 3
    assert metrics.dominant_source_type_fraction == pytest.approx(
        1 / 3
    )


def test_unresolved_calibration_never_invents_routing_booleans():
    curation, brief = make_curation_and_brief()
    metrics = build_evidence_quality_metrics(curation, brief)

    signals = assess_evidence_quality_signals(metrics)

    assert signals.evidence_sparse is None
    assert signals.evidence_ambiguous is None
    assert signals.source_diversity_low is None
    assert signals.routing_ready is False
    assert signals.unresolved_signal_names == [
        "evidence_sparse",
        "evidence_ambiguous",
        "source_diversity_low",
    ]


def test_calibrated_thresholds_resolve_available_signals():
    curation, brief = make_curation_and_brief()
    metrics = build_evidence_quality_metrics(curation, brief)

    signals = assess_evidence_quality_signals(
        metrics,
        EvidenceQualityThresholds(
            calibration_status="calibrated",
            sparse_direct_source_threshold=4,
            ambiguity_top_margin_threshold=10.0,
            low_diversity_fraction_threshold=0.8,
        ),
    )

    assert signals.evidence_sparse is True
    assert signals.evidence_ambiguous is True
    assert signals.source_diversity_low is False
    assert signals.unresolved_signal_names == []


def test_top_direct_margin_resolves_when_two_direct_sources_exist():
    curation = curate_evidence(
        evidence_items=[
            {
                "source_type": "research_paper",
                "title": (
                    "Retrieval Augmented Generation for Question Answering"
                ),
                "abstract": (
                    "Retrieval augmented generation improves question "
                    "answering."
                ),
            },
            {
                "source_type": "research_paper",
                "title": (
                    "Question Answering with Retrieval Augmented Context"
                ),
                "abstract": (
                    "Question answering benefits from retrieval "
                    "augmented context."
                ),
            },
        ],
        user_query=(
            "Build a retrieval augmented generation project for "
            "question answering"
        ),
    )
    brief = build_evidence_brief(
        evidence_items=[
            {
                **entry.item,
                "support_scope": entry.support_scope,
            }
            for entry in curation.retained
        ],
        user_query=curation.required_anchor_terms[0],
    )
    metrics = build_evidence_quality_metrics(curation, brief)

    assert metrics.top_direct_relevance_margin is not None

    signals = assess_evidence_quality_signals(
        metrics,
        EvidenceQualityThresholds(
            calibration_status="calibrated",
            sparse_direct_source_threshold=1,
            ambiguity_top_margin_threshold=metrics.top_direct_relevance_margin,
            low_diversity_fraction_threshold=1.0,
        ),
    )

    assert signals.evidence_ambiguous is True
    assert signals.routing_ready is True


def test_rejects_partial_or_invalid_calibration():
    with pytest.raises(ValueError, match="Unresolved calibration"):
        EvidenceQualityThresholds(
            calibration_status="unresolved",
            sparse_direct_source_threshold=1,
        ).validate()

    with pytest.raises(ValueError, match="require all"):
        EvidenceQualityThresholds(
            calibration_status="calibrated",
            sparse_direct_source_threshold=1,
        ).validate()

    with pytest.raises(ValueError, match="between 0 and 1"):
        EvidenceQualityThresholds(
            calibration_status="calibrated",
            sparse_direct_source_threshold=1,
            ambiguity_top_margin_threshold=0.2,
            low_diversity_fraction_threshold=1.1,
        ).validate()
