from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


VALID_GROUNDING_CLASSES = {
    "cited_with_direct_scope",
    "cited_only_adjacent",
    "uncited_covered",
    "uncited_sparse",
    "invalid_citations",
}


@dataclass(frozen=True)
class EvidenceAvailabilitySignals:
    """
    Evidence-stage signals used only for degradation decisions.

    These values will later be produced by the adaptive evidence-quality
    layer. They are intentionally separate from candidate ranking and
    validation.
    """

    direct_source_count: int
    adjacent_source_count: int
    query_aligned_source_count: int

    def validate(self) -> None:
        values = {
            "direct_source_count": self.direct_source_count,
            "adjacent_source_count": self.adjacent_source_count,
            "query_aligned_source_count": (
                self.query_aligned_source_count
            ),
        }

        for name, value in values.items():
            if value < 0:
                raise ValueError(f"{name} cannot be negative.")

    def to_dict(self) -> Dict[str, int]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class DegradationPolicy:
    """
    Versioned product policy for honest weak-evidence behavior.

    The initial constants are explicit product defaults, not calibrated
    corpus thresholds. They will be revisited after evidence-signal
    distributions are measured across a larger evaluation set.
    """

    version: str = "v1"
    min_adjacent_sources_for_limited_response: int = 2
    exploratory_max_directions: int = 2
    limited_max_directions: int = 3
    standard_max_directions: int = 3
    no_query_aligned_sources_forces_exploratory: bool = True
    all_uncited_candidates_block_live_promotion: bool = True

    def validate(self) -> None:
        if not self.version.strip():
            raise ValueError("Degradation policy version must be non-empty.")

        if self.min_adjacent_sources_for_limited_response < 1:
            raise ValueError(
                "min_adjacent_sources_for_limited_response must be at least 1."
            )

        for name, value in {
            "exploratory_max_directions": (
                self.exploratory_max_directions
            ),
            "limited_max_directions": self.limited_max_directions,
            "standard_max_directions": self.standard_max_directions,
        }.items():
            if value < 1:
                raise ValueError(f"{name} must be at least 1.")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class DegradationDecision:
    response_quality: str
    evidence_confidence: str
    max_directions: int
    reason_codes: List[str] = field(default_factory=list)
    user_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assess_evidence_degradation(
    signals: EvidenceAvailabilitySignals,
    policy: Optional[DegradationPolicy] = None,
) -> DegradationDecision:
    """
    Decide how honestly the product should frame evidence quality before
    candidate generation.

    This does not alter retrieval, selection, ranking, or model routing.
    It defines the response contract the future routing layer must honor.
    """
    signals.validate()
    policy = policy or DegradationPolicy()
    policy.validate()

    reason_codes: List[str] = []

    if (
        policy.no_query_aligned_sources_forces_exploratory
        and signals.query_aligned_source_count == 0
    ):
        reason_codes.append("no_query_aligned_sources")

    if signals.direct_source_count == 0:
        reason_codes.append("no_direct_sources")

    if (
        signals.direct_source_count == 0
        and signals.adjacent_source_count
        < policy.min_adjacent_sources_for_limited_response
    ):
        reason_codes.append("insufficient_adjacent_sources")

    if reason_codes and (
        "no_query_aligned_sources" in reason_codes
        or "insufficient_adjacent_sources" in reason_codes
    ):
        return DegradationDecision(
            response_quality="exploratory",
            evidence_confidence="exploratory",
            max_directions=policy.exploratory_max_directions,
            reason_codes=reason_codes,
            user_message=(
                "Direct evidence is limited for this request. These "
                "directions should be treated as exploratory starting "
                "points rather than strongly research-backed recommendations."
            ),
        )

    if signals.direct_source_count == 0:
        return DegradationDecision(
            response_quality="limited",
            evidence_confidence="limited",
            max_directions=policy.limited_max_directions,
            reason_codes=reason_codes,
            user_message=(
                "Direct research evidence was unavailable, so these "
                "directions rely on adjacent technical context and should "
                "be validated before implementation."
            ),
        )

    return DegradationDecision(
        response_quality="standard",
        evidence_confidence="strong",
        max_directions=policy.standard_max_directions,
        reason_codes=[],
        user_message="",
    )


def all_candidates_uncited_blocks_promotion(
    grounding_classes: Sequence[str],
    policy: Optional[DegradationPolicy] = None,
) -> bool:
    """
    Post-planning safety check. It is kept separate from evidence-stage
    routing because it depends on candidate grounding outcomes.
    """
    policy = policy or DegradationPolicy()
    policy.validate()

    normalized = [
        str(value).strip()
        for value in grounding_classes
        if str(value).strip()
    ]

    if not normalized:
        return False

    invalid = [
        value
        for value in normalized
        if value not in VALID_GROUNDING_CLASSES
    ]

    if invalid:
        raise ValueError(
            "Unknown grounding classes: " + ", ".join(sorted(set(invalid)))
        )

    uncited_classes = {
        "uncited_covered",
        "uncited_sparse",
    }

    return (
        policy.all_uncited_candidates_block_live_promotion
        and all(value in uncited_classes for value in normalized)
    )
