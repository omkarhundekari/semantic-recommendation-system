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
