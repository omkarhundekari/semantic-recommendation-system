from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List


class EvidenceBudgetRoute(str, Enum):
    STANDARD = "standard"
    FULL_INCLUSION = "full_inclusion"
    EXPANDED = "expanded"
    DIVERSITY_BOOST = "diversity_boost"


@dataclass(frozen=True)
class EvidenceRoutingSignals:
    """
    Normalized routing inputs.

    This contract intentionally accepts already-computed boolean signals.
    Signal definitions, thresholds, and corpus calibration belong to the
    future evidence-quality layer rather than this policy module.
    """

    evidence_sparse: bool
    evidence_ambiguous: bool
    source_diversity_low: bool

    def to_dict(self) -> Dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceRoutingDecision:
    policy_version: str
    route: EvidenceBudgetRoute
    reason_codes: List[str]
    precedence_rule: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["route"] = self.route.value
        return payload


@dataclass(frozen=True)
class EvidenceRoutingPolicy:
    """
    Deterministic route-precedence contract.

    Precedence:
    expanded > diversity_boost > full_inclusion > standard

    The policy chooses a context-handling route only. It does not retrieve,
    compress, rank, or discard evidence by itself.
    """

    version: str = "v1"

    def to_dict(self) -> Dict[str, str]:
        return {"version": self.version}


def route_evidence_budget(
    signals: EvidenceRoutingSignals,
    policy: EvidenceRoutingPolicy = None,
) -> EvidenceRoutingDecision:
    """
    Resolve a deterministic evidence route from calibrated boolean signals.

    Decision table:
      sparse  ambiguous  diversity_low  -> route
      False   False      False          -> standard
      True    False      False          -> full_inclusion
      False   True       False          -> expanded
      False   False      True           -> diversity_boost
      True    True       False          -> expanded
      True    False      True           -> diversity_boost
      False   True       True           -> expanded
      True    True       True           -> expanded
    """
    policy = policy or EvidenceRoutingPolicy()

    reason_codes = []

    if signals.evidence_sparse:
        reason_codes.append("evidence_sparse")

    if signals.evidence_ambiguous:
        reason_codes.append("evidence_ambiguous")

    if signals.source_diversity_low:
        reason_codes.append("source_diversity_low")

    if signals.evidence_ambiguous:
        return EvidenceRoutingDecision(
            policy_version=policy.version,
            route=EvidenceBudgetRoute.EXPANDED,
            reason_codes=reason_codes,
            precedence_rule=(
                "expanded takes precedence when evidence is ambiguous."
            ),
        )

    if signals.source_diversity_low:
        return EvidenceRoutingDecision(
            policy_version=policy.version,
            route=EvidenceBudgetRoute.DIVERSITY_BOOST,
            reason_codes=reason_codes,
            precedence_rule=(
                "diversity_boost takes precedence over full_inclusion."
            ),
        )

    if signals.evidence_sparse:
        return EvidenceRoutingDecision(
            policy_version=policy.version,
            route=EvidenceBudgetRoute.FULL_INCLUSION,
            reason_codes=reason_codes,
            precedence_rule=(
                "full_inclusion applies when evidence is sparse but "
                "not ambiguous or diversity-concentrated."
            ),
        )

    return EvidenceRoutingDecision(
        policy_version=policy.version,
        route=EvidenceBudgetRoute.STANDARD,
        reason_codes=[],
        precedence_rule=(
            "standard applies when no evidence-quality escalation signal "
            "is active."
        ),
    )


def route_calibrated_evidence_quality(
    quality_signals,
    policy: EvidenceRoutingPolicy = None,
) -> EvidenceRoutingDecision:
    """
    Route only fully resolved evidence-quality signals.

    Unresolved calibration or missing metrics must remain visible in shadow
    diagnostics rather than silently taking the standard route.
    """
    if not quality_signals.routing_ready:
        unresolved = ", ".join(
            quality_signals.unresolved_signal_names
        )
        raise ValueError(
            "Evidence routing requires resolved quality signals. "
            f"Unresolved: {unresolved or 'unknown'}."
        )

    return route_evidence_budget(
        EvidenceRoutingSignals(
            evidence_sparse=quality_signals.evidence_sparse,
            evidence_ambiguous=quality_signals.evidence_ambiguous,
            source_diversity_low=quality_signals.source_diversity_low,
        ),
        policy=policy,
    )
