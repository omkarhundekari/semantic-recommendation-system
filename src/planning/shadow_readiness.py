from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from planning.evidence_curation import EvidenceCurationResult
from planning.planner_models import EvidenceBrief
from planning.planning_orchestrator import PlanningOutcome


@dataclass
class ShadowReadinessAssessment:
    status: str
    reasons: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assess_shadow_readiness(
    curation: EvidenceCurationResult,
    brief: EvidenceBrief,
    outcome: PlanningOutcome,
) -> ShadowReadinessAssessment:
    signals = {
        "raw_evidence_count": (
            len(curation.retained) + len(curation.dropped)
        ),
        "curated_evidence_count": len(curation.retained),
        "dropped_evidence_count": len(curation.dropped),
        "generated_candidate_count": len(
            outcome.generated_candidates
        ),
        "valid_candidate_count": len(outcome.valid_candidates),
        "selected_candidate_count": len(
            outcome.selected_candidates
        ),
        "provider_called": outcome.provider_called,
        "coverage_warnings": list(brief.coverage_warnings),
        "validation_errors": list(outcome.validation_errors),
        "validation_warnings": list(
            outcome.validation_warnings
        ),
    }

    blocked_reasons = []

    if not outcome.provider_called:
        blocked_reasons.append(
            "Candidate generation provider was not called."
        )

    if not curation.retained:
        blocked_reasons.append(
            "No curated evidence remained after relevance curation."
        )

    if not outcome.valid_candidates:
        blocked_reasons.append(
            "No valid candidate directions were produced."
        )

    if not outcome.selected_candidates:
        blocked_reasons.append(
            "No ranked candidate directions were selected."
        )

    if blocked_reasons:
        return ShadowReadinessAssessment(
            status="blocked",
            reasons=blocked_reasons,
            signals=signals,
        )

    review_reasons = []

    if brief.coverage_warnings:
        review_reasons.extend(brief.coverage_warnings)

    if outcome.validation_errors:
        review_reasons.append(
            "Some generated candidates failed validation."
        )

    if outcome.validation_warnings:
        review_reasons.append(
            "Selected candidates include validation warnings."
        )

    if review_reasons:
        return ShadowReadinessAssessment(
            status="needs_review",
            reasons=review_reasons,
            signals=signals,
        )

    return ShadowReadinessAssessment(
        status="ready",
        reasons=[
            "Curated evidence, validated candidates, and selected "
            "directions are available without coverage or validation "
            "warnings."
        ],
        signals=signals,
    )
