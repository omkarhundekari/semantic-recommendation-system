import pytest

from planning.degradation_policy import (
    DegradationPolicy,
    EvidenceAvailabilitySignals,
    all_candidates_uncited_blocks_promotion,
    assess_evidence_degradation,
)


def test_standard_response_when_direct_and_query_aligned_evidence_exists():
    decision = assess_evidence_degradation(
        EvidenceAvailabilitySignals(
            direct_source_count=3,
            adjacent_source_count=2,
            query_aligned_source_count=2,
        )
    )

    assert decision.response_quality == "standard"
    assert decision.evidence_confidence == "strong"
    assert decision.max_directions == 3
    assert decision.reason_codes == []


def test_limited_response_when_direct_sources_are_missing_but_adjacent_exist():
    decision = assess_evidence_degradation(
        EvidenceAvailabilitySignals(
            direct_source_count=0,
            adjacent_source_count=3,
            query_aligned_source_count=2,
        )
    )

    assert decision.response_quality == "limited"
    assert decision.evidence_confidence == "limited"
    assert decision.reason_codes == ["no_direct_sources"]


def test_exploratory_response_when_evidence_is_sparse():
    decision = assess_evidence_degradation(
        EvidenceAvailabilitySignals(
            direct_source_count=0,
            adjacent_source_count=1,
            query_aligned_source_count=1,
        )
    )

    assert decision.response_quality == "exploratory"
    assert decision.evidence_confidence == "exploratory"
    assert decision.max_directions == 2
    assert decision.reason_codes == [
        "no_direct_sources",
        "insufficient_adjacent_sources",
    ]


def test_no_query_alignment_forces_exploratory_response():
    decision = assess_evidence_degradation(
        EvidenceAvailabilitySignals(
            direct_source_count=4,
            adjacent_source_count=2,
            query_aligned_source_count=0,
        )
    )

    assert decision.response_quality == "exploratory"
    assert "no_query_aligned_sources" in decision.reason_codes


def test_all_uncited_candidates_block_promotion_but_mixed_grounding_does_not():
    assert all_candidates_uncited_blocks_promotion(
        ["uncited_covered", "uncited_sparse"]
    ) is True

    assert all_candidates_uncited_blocks_promotion(
        ["uncited_covered", "cited_with_direct_scope"]
    ) is False


def test_rejects_invalid_signal_counts_and_unknown_grounding_classes():
    with pytest.raises(ValueError, match="cannot be negative"):
        assess_evidence_degradation(
            EvidenceAvailabilitySignals(
                direct_source_count=-1,
                adjacent_source_count=0,
                query_aligned_source_count=0,
            )
        )

    with pytest.raises(ValueError, match="Unknown grounding classes"):
        all_candidates_uncited_blocks_promotion(["unknown_class"])


def test_policy_is_versioned_and_configurable():
    policy = DegradationPolicy(
        version="v1-test",
        exploratory_max_directions=1,
    )

    decision = assess_evidence_degradation(
        EvidenceAvailabilitySignals(
            direct_source_count=0,
            adjacent_source_count=0,
            query_aligned_source_count=0,
        ),
        policy=policy,
    )

    assert policy.to_dict()["version"] == "v1-test"
    assert decision.max_directions == 1
