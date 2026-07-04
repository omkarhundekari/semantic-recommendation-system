from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


EXPECTED_DIFFICULTIES = {"Easy", "Medium", "Hard"}
CRITICAL_CHECKS = (
    "evidence_present",
    "no_banned_stack",
)


@dataclass
class ProductPlanReadinessAssessment:
    status: str
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _source_counts(evidence_items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}

    for item in evidence_items:
        source_type = str(item.get("source_type") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + 1

    return counts


def _portfolio_difficulties(ideas: List[Dict[str, Any]]) -> List[str]:
    difficulties = []

    for idea in ideas:
        profile = (
            idea.get("feasibility_analysis", {})
            .get("build_profile", {})
        )
        difficulty = str(profile.get("difficulty") or "").strip()

        if difficulty:
            difficulties.append(difficulty)

    return difficulties


def _research_signals(
    assessment: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    confidence = (assessment or {}).get("confidence", {})
    evidence = (assessment or {}).get("evidence", {})
    alignment = evidence.get("alignment_summary", {})

    return {
        "research_confidence_level": confidence.get("level"),
        "research_confidence_reason": confidence.get("reason"),
        "direct_research_support_count": int(alignment.get("direct", 0)),
        "adjacent_research_support_count": int(
            alignment.get("adjacent", 0)
        ),
        "weak_research_support_count": int(alignment.get("weak", 0)),
    }


def assess_product_plan_readiness(
    evidence_items: List[Dict[str, Any]],
    ideas: List[Dict[str, Any]],
    verification_results: List[Dict[str, Any]],
    repairs_by_index: List[List[str]],
    research_evidence_assessment: Optional[Dict[str, Any]] = None,
) -> ProductPlanReadinessAssessment:
    source_counts = _source_counts(evidence_items)
    portfolio_difficulties = _portfolio_difficulties(ideas)
    research_signals = _research_signals(
        research_evidence_assessment
    )

    warning_count = sum(
        len(result.get("warnings", []))
        for result in verification_results
    )
    repair_count = sum(len(repairs) for repairs in repairs_by_index)

    signals = {
        "focused_evidence_count": len(evidence_items),
        "source_counts": source_counts,
        "direction_count": len(ideas),
        "portfolio_difficulties": portfolio_difficulties,
        "verification_result_count": len(verification_results),
        "verification_warning_count": warning_count,
        "repair_count": repair_count,
        **research_signals,
    }

    blocked_reasons = []

    if not evidence_items:
        blocked_reasons.append(
            "Focused evidence retrieval returned no usable items."
        )

    if len(ideas) != 3:
        blocked_reasons.append(
            f"Expected three portfolio directions, received {len(ideas)}."
        )

    if len(verification_results) != len(ideas):
        blocked_reasons.append(
            "Final verification results do not cover every direction."
        )

    if set(portfolio_difficulties) != EXPECTED_DIFFICULTIES:
        blocked_reasons.append(
            "Portfolio ladder did not produce Easy, Medium, and Hard directions."
        )

    for check_name in CRITICAL_CHECKS:
        if any(
            not result.get("checks", {}).get(check_name, False)
            for result in verification_results
        ):
            if check_name == "evidence_present":
                blocked_reasons.append(
                    "At least one direction is missing a visible evidence reference."
                )
            elif check_name == "no_banned_stack":
                blocked_reasons.append(
                    "At least one direction still contains a prototype-only stack dependency."
                )

    if blocked_reasons:
        return ProductPlanReadinessAssessment(
            status="blocked",
            reasons=blocked_reasons,
            signals=signals,
        )

    review_reasons = []

    if warning_count:
        review_reasons.append(
            f"{warning_count} final verification warning(s) remain."
        )

    confidence_level = research_signals["research_confidence_level"]
    direct_support_count = research_signals[
        "direct_research_support_count"
    ]

    if confidence_level in {"limited", "exploratory"}:
        review_reasons.append(
            f"Research evidence is {confidence_level}, so the plan should "
            "be reviewed with its source context."
        )

    if (
        research_evidence_assessment is not None
        and direct_support_count == 0
    ):
        review_reasons.append(
            "No direct research support was identified in the focused "
            "research evidence."
        )

    if review_reasons:
        return ProductPlanReadinessAssessment(
            status="needs_review",
            reasons=review_reasons,
            signals=signals,
        )

    return ProductPlanReadinessAssessment(
        status="ready",
        reasons=[
            "Three verified portfolio directions were produced from focused "
            "evidence with complete Easy, Medium, and Hard coverage."
        ],
        signals=signals,
    )
