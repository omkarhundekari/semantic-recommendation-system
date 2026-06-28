from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from planning.candidate_models import CandidateGenerationRequest
from planning.generation_provider import CandidateGenerationProvider
from planning.planning_orchestrator import PlanningOutcome, plan_candidates
from planning.evidence_brief import build_evidence_brief


@dataclass
class ShadowPlanningReport:
    evidence_brief: Dict[str, Any]
    planning_diagnostics: Dict[str, Any]
    selected_titles: List[str]
    legacy_titles: List[str]
    comparison: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_generation_request(
    user_goal: str,
    constraints: Optional[Dict[str, Any]] = None,
) -> CandidateGenerationRequest:
    constraints = constraints or {}

    return CandidateGenerationRequest(
        user_goal=user_goal,
        skill_level=str(constraints.get("skill_level") or ""),
        time_available=str(constraints.get("time_available") or ""),
        target_roles=list(constraints.get("target_roles") or []),
        preferred_stack=list(constraints.get("preferred_stack") or []),
    )


def _legacy_titles(legacy_ideas: Optional[List[Dict[str, Any]]]) -> List[str]:
    return [
        str(idea.get("project_title", "")).strip()
        for idea in (legacy_ideas or [])
        if str(idea.get("project_title", "")).strip()
    ]


def run_shadow_plan(
    evidence_items: List[Dict[str, Any]],
    user_goal: str,
    constraints: Optional[Dict[str, Any]],
    provider: CandidateGenerationProvider,
    legacy_ideas: Optional[List[Dict[str, Any]]] = None,
    max_candidates: int = 3,
) -> ShadowPlanningReport:
    brief = build_evidence_brief(
        evidence_items=evidence_items,
        user_query=user_goal,
    )
    request = build_generation_request(
        user_goal=user_goal,
        constraints=constraints,
    )

    outcome: PlanningOutcome = plan_candidates(
        brief=brief,
        request=request,
        provider=provider,
        max_candidates=max_candidates,
    )

    selected_titles = [
        ranked.candidate.title
        for ranked in outcome.selected_candidates
    ]
    legacy_titles = _legacy_titles(legacy_ideas)

    comparison = {
        "legacy_direction_count": len(legacy_titles),
        "v2_generated_candidate_count": len(
            outcome.generated_candidates
        ),
        "v2_valid_candidate_count": len(
            outcome.valid_candidates
        ),
        "v2_selected_candidate_count": len(
            outcome.selected_candidates
        ),
        "v2_selected_titles": selected_titles,
        "provider_called": outcome.provider_called,
        "coverage_warnings": list(brief.coverage_warnings),
    }

    return ShadowPlanningReport(
        evidence_brief=brief.to_dict(),
        planning_diagnostics=outcome.diagnostics(),
        selected_titles=selected_titles,
        legacy_titles=legacy_titles,
        comparison=comparison,
    )
