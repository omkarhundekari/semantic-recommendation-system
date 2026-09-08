from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planning.candidate_generation_service import (
    generate_validated_candidates,
)
from planning.candidate_models import CandidateDirection
from planning.candidate_set_gate import assess_candidate_set
from planning.evidence_brief import build_evidence_brief
from planning.evidence_curation import curate_evidence
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.generation_provider import CandidateGenerationProvider
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.planning_orchestrator import plan_candidates
from planning.shadow_runner import build_generation_request


REQUIRED_CANDIDATE_COUNT = 3


@dataclass
class SuccessorPlanningResult:
    status: str
    candidates: List[CandidateDirection] = field(
        default_factory=list
    )
    assessment: Optional[Dict[str, Any]] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def _result(
    status: str,
    diagnostics: Optional[Dict[str, Any]] = None,
    assessment: Optional[Dict[str, Any]] = None,
) -> SuccessorPlanningResult:
    details = dict(diagnostics or {})
    details["reason_code"] = status

    return SuccessorPlanningResult(
        status=status,
        candidates=[],
        assessment=assessment,
        diagnostics=details,
    )


def build_successor_plan(
    evidence_items: List[Dict[str, Any]],
    user_goal: str,
    constraints: Optional[Dict[str, Any]],
    detected_domain: Optional[str],
    provider: CandidateGenerationProvider,
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: Optional[
        SemanticCandidateDiversityScorer
    ],
) -> SuccessorPlanningResult:
    curation = curate_evidence(
        evidence_items=evidence_items,
        user_query=user_goal,
    )
    curated_items = [
        {
            **entry.item,
            "support_scope": entry.support_scope,
            "retention_reason": entry.retention_reason,
        }
        for entry in curation.retained
    ]

    brief = build_evidence_brief(
        evidence_items=curated_items,
        user_query=user_goal,
    )
    request = build_generation_request(
        user_goal=user_goal,
        constraints=constraints,
    )

    try:
        generation = generate_validated_candidates(
            brief=brief,
            request=request,
            provider=provider,
        )
    except ValueError:
        return _result("provider_invalid_output")
    except RuntimeError:
        return _result("provider_error")

    outcome = plan_candidates(
        brief=brief,
        request=request,
        provider=provider,
        max_candidates=REQUIRED_CANDIDATE_COUNT,
        generation=generation,
    )

    diagnostics = outcome.diagnostics()
    diagnostics["required_candidate_count"] = (
        REQUIRED_CANDIDATE_COUNT
    )

    if not outcome.valid_candidates:
        return _result(
            "no_valid_candidates",
            diagnostics,
        )

    if (
        len(outcome.selected_candidates)
        != REQUIRED_CANDIDATE_COUNT
    ):
        return _result(
            "insufficient_candidates",
            diagnostics,
        )

    selected = [
        ranked.candidate
        for ranked in outcome.selected_candidates
    ]

    gate = assess_candidate_set(
        candidates=selected,
        brief=brief,
        request=request,
        detected_domain=detected_domain,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )
    assessment = gate.to_dict()

    diagnostics["gate_status"] = gate.status
    diagnostics["reason_code"] = gate.status

    if gate.status != "ready":
        return _result(
            gate.status,
            diagnostics,
            assessment=assessment,
        )

    return SuccessorPlanningResult(
        status="ready",
        candidates=selected,
        assessment=assessment,
        diagnostics=diagnostics,
    )
