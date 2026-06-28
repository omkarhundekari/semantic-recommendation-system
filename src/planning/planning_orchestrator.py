from dataclasses import dataclass, field
from typing import Dict, List

from planning.candidate_generation_service import (
    CandidateGenerationOutcome,
    generate_validated_candidates,
)
from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_ranker import (
    RankedCandidate,
    rank_candidates,
    select_diverse_candidates,
)
from planning.generation_provider import CandidateGenerationProvider
from planning.planner_models import EvidenceBrief


@dataclass
class PlanningOutcome:
    generated_candidates: List[CandidateDirection] = field(
        default_factory=list
    )
    valid_candidates: List[CandidateDirection] = field(
        default_factory=list
    )
    ranked_candidates: List[RankedCandidate] = field(
        default_factory=list
    )
    selected_candidates: List[RankedCandidate] = field(
        default_factory=list
    )
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    provider_called: bool = False

    def diagnostics(self) -> Dict:
        return {
            "generated_candidate_count": len(
                self.generated_candidates
            ),
            "valid_candidate_count": len(self.valid_candidates),
            "selected_candidate_count": len(
                self.selected_candidates
            ),
            "validation_errors": list(self.validation_errors),
            "validation_warnings": list(
                self.validation_warnings
            ),
            "provider_called": self.provider_called,
        }


def plan_candidates(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    provider: CandidateGenerationProvider,
    max_candidates: int = 3,
) -> PlanningOutcome:
    generation: CandidateGenerationOutcome = (
        generate_validated_candidates(
            brief=brief,
            request=request,
            provider=provider,
        )
    )

    validation_errors = []
    validation_warnings = []

    for validation in generation.validations:
        validation_errors.extend(validation.errors)
        validation_warnings.extend(validation.warnings)

    valid_candidates = generation.valid_candidates

    if not valid_candidates:
        return PlanningOutcome(
            generated_candidates=generation.candidates,
            valid_candidates=[],
            ranked_candidates=[],
            selected_candidates=[],
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            provider_called=generation.provider_called,
        )

    ranked_candidates = rank_candidates(
        candidates=valid_candidates,
        brief=brief,
        request=request,
    )
    selected_candidates = select_diverse_candidates(
        ranked_candidates=ranked_candidates,
        max_candidates=max_candidates,
    )

    return PlanningOutcome(
        generated_candidates=generation.candidates,
        valid_candidates=valid_candidates,
        ranked_candidates=ranked_candidates,
        selected_candidates=selected_candidates,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        provider_called=generation.provider_called,
    )
