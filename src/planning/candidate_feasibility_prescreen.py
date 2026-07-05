from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from feasibility_scorer import score_project_feasibility
from plan_verifier import verify_project_ideas
from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_to_product_adapter import (
    adapt_candidate_to_product_idea,
)
from planning.planner_models import EvidenceBrief


@dataclass(frozen=True)
class CandidateFeasibilityPrescreen:
    candidate_title: str
    status: str
    feasibility_analysis: Dict[str, Any]
    verification: Dict[str, Any]
    blocking_reasons: List[str]
    review_reasons: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _constraints_from_request(
    request: CandidateGenerationRequest,
) -> Dict[str, Any]:
    return {
        "skill_level": request.skill_level,
        "time_available": request.time_available,
        "target_roles": list(request.target_roles),
        "preferred_stack": list(request.preferred_stack),
    }


def prescreen_candidate_feasibility(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    detected_domain: str,
) -> CandidateFeasibilityPrescreen:
    """
    Reuse the same adapter, feasibility scorer, and verifier used by
    deterministic product enrichment. This does not repair or mutate a
    candidate; it only records whether its current scope fits constraints.
    """
    constraints = _constraints_from_request(request)

    idea = adapt_candidate_to_product_idea(
        candidate=candidate,
        brief=brief,
        detected_domain=detected_domain or "general",
        target_roles=list(request.target_roles),
    )
    feasibility_analysis = score_project_feasibility(idea)
    idea["feasibility_analysis"] = feasibility_analysis

    verification = verify_project_ideas(
        [idea],
        constraints,
    )[0]

    checks = verification.get("checks", {})
    warnings = list(verification.get("warnings", []))

    blocking_reasons = []

    if not checks.get("time_feasibility", True):
        blocking_reasons.append(
            "Candidate scope exceeds the stated timeline."
        )

    if not checks.get("no_banned_stack", True):
        blocking_reasons.append(
            "Candidate includes a prototype-only stack dependency."
        )

    review_reasons = []

    review_checks = {
        "role_alignment": (
            "Candidate does not clearly match the requested target role."
        ),
        "preferred_stack_alignment": (
            "Candidate does not reflect the preferred technology stack."
        ),
        "specific_mvp_language": (
            "Candidate MVP still contains generic template language."
        ),
        "evidence_present": (
            "Candidate has no visible evidence reference after adaptation."
        ),
    }

    for check_name, message in review_checks.items():
        if not checks.get(check_name, True):
            review_reasons.append(message)

    normalized_warning_markers = {
        "role_alignment": [
            "target role",
            "target roles",
        ],
        "preferred_stack_alignment": [
            "preferred technology stack",
            "preferred stack",
        ],
        "specific_mvp_language": [
            "generic",
            "template language",
        ],
        "evidence_present": [
            "evidence",
            "research reference",
        ],
    }

    for warning in warnings:
        warning_text = str(warning).strip()
        warning_lower = warning_text.lower()

        duplicates_canonical_reason = any(
            not checks.get(check_name, True)
            and any(
                marker in warning_lower
                for marker in markers
            )
            for check_name, markers
            in normalized_warning_markers.items()
        )

        if (
            warning_text
            and warning_text not in blocking_reasons
            and warning_text not in review_reasons
            and not duplicates_canonical_reason
        ):
            review_reasons.append(warning_text)

    if blocking_reasons:
        status = "blocked_by_constraints"
    elif review_reasons:
        status = "needs_review"
    else:
        status = "feasible"

    return CandidateFeasibilityPrescreen(
        candidate_title=candidate.title,
        status=status,
        feasibility_analysis=feasibility_analysis,
        verification=verification,
        blocking_reasons=blocking_reasons,
        review_reasons=review_reasons,
    )
