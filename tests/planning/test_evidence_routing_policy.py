import pytest

from planning.evidence_routing_policy import (
    EvidenceBudgetRoute,
    EvidenceRoutingPolicy,
    EvidenceRoutingSignals,
    route_evidence_budget,
)


@pytest.mark.parametrize(
    (
        "evidence_sparse",
        "evidence_ambiguous",
        "source_diversity_low",
        "expected_route",
    ),
    [
        (False, False, False, EvidenceBudgetRoute.STANDARD),
        (True, False, False, EvidenceBudgetRoute.FULL_INCLUSION),
        (False, True, False, EvidenceBudgetRoute.EXPANDED),
        (False, False, True, EvidenceBudgetRoute.DIVERSITY_BOOST),
        (True, True, False, EvidenceBudgetRoute.EXPANDED),
        (True, False, True, EvidenceBudgetRoute.DIVERSITY_BOOST),
        (False, True, True, EvidenceBudgetRoute.EXPANDED),
        (True, True, True, EvidenceBudgetRoute.EXPANDED),
    ],
)
def test_routing_truth_table(
    evidence_sparse,
    evidence_ambiguous,
    source_diversity_low,
    expected_route,
):
    decision = route_evidence_budget(
        EvidenceRoutingSignals(
            evidence_sparse=evidence_sparse,
            evidence_ambiguous=evidence_ambiguous,
            source_diversity_low=source_diversity_low,
        )
    )

    assert decision.route == expected_route


def test_ambiguous_evidence_has_highest_route_precedence():
    decision = route_evidence_budget(
        EvidenceRoutingSignals(
            evidence_sparse=True,
            evidence_ambiguous=True,
            source_diversity_low=True,
        )
    )

    assert decision.route == EvidenceBudgetRoute.EXPANDED
    assert decision.reason_codes == [
        "evidence_sparse",
        "evidence_ambiguous",
        "source_diversity_low",
    ]


def test_diversity_boost_precedes_full_inclusion():
    decision = route_evidence_budget(
        EvidenceRoutingSignals(
            evidence_sparse=True,
            evidence_ambiguous=False,
            source_diversity_low=True,
        )
    )

    assert decision.route == EvidenceBudgetRoute.DIVERSITY_BOOST


def test_policy_version_is_preserved_in_decision_payload():
    decision = route_evidence_budget(
        EvidenceRoutingSignals(
            evidence_sparse=False,
            evidence_ambiguous=False,
            source_diversity_low=False,
        ),
        policy=EvidenceRoutingPolicy(version="v1-test"),
    )

    payload = decision.to_dict()

    assert payload["policy_version"] == "v1-test"
    assert payload["route"] == "standard"


def test_routing_gate_rejects_unresolved_quality_signals():
    import pytest

    from planning.evidence_quality_signals import (
        EvidenceQualityMetrics,
        EvidenceQualitySignals,
        EvidenceQualityThresholds,
    )
    from planning.evidence_routing_policy import (
        route_calibrated_evidence_quality,
    )

    metrics = EvidenceQualityMetrics(
        curation_pool_size=1,
        retained_source_count=1,
        final_brief_source_count=1,
        direct_source_count=1,
        adjacent_source_count=0,
        required_anchor_count=0,
        matched_required_anchor_count=0,
        query_anchor_coverage=None,
        unique_query_term_count=0,
        unique_query_phrase_count=0,
        source_type_count=1,
        dominant_source_type="research_paper",
        dominant_source_type_fraction=1.0,
        top_direct_relevance_margin=None,
        coverage_warnings=[],
    )

    signals = EvidenceQualitySignals(
        metrics=metrics,
        thresholds=EvidenceQualityThresholds(),
        evidence_sparse=None,
        evidence_ambiguous=None,
        source_diversity_low=None,
        unresolved_signal_names=[
            "evidence_sparse",
            "evidence_ambiguous",
            "source_diversity_low",
        ],
    )

    with pytest.raises(ValueError, match="requires resolved"):
        route_calibrated_evidence_quality(signals)


def test_routing_gate_uses_resolved_quality_signals():
    from planning.evidence_quality_signals import (
        EvidenceQualityMetrics,
        EvidenceQualitySignals,
        EvidenceQualityThresholds,
    )
    from planning.evidence_routing_policy import (
        route_calibrated_evidence_quality,
    )

    metrics = EvidenceQualityMetrics(
        curation_pool_size=4,
        retained_source_count=3,
        final_brief_source_count=3,
        direct_source_count=1,
        adjacent_source_count=2,
        required_anchor_count=0,
        matched_required_anchor_count=0,
        query_anchor_coverage=None,
        unique_query_term_count=2,
        unique_query_phrase_count=1,
        source_type_count=2,
        dominant_source_type="research_paper",
        dominant_source_type_fraction=2 / 3,
        top_direct_relevance_margin=0.2,
        coverage_warnings=[],
    )

    signals = EvidenceQualitySignals(
        metrics=metrics,
        thresholds=EvidenceQualityThresholds(
            calibration_status="calibrated",
            sparse_direct_source_threshold=2,
            ambiguity_top_margin_threshold=0.1,
            low_diversity_fraction_threshold=0.9,
        ),
        evidence_sparse=True,
        evidence_ambiguous=False,
        source_diversity_low=False,
    )

    decision = route_calibrated_evidence_quality(signals)

    assert decision.route == EvidenceBudgetRoute.FULL_INCLUSION
