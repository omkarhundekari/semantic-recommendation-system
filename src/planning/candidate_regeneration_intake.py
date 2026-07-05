from dataclasses import dataclass
from typing import Any

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.candidate_parser import parse_single_candidate_payload
from planning.candidate_validator import validate_candidate
from planning.planner_models import EvidenceBrief


@dataclass(frozen=True)
class RegeneratedCandidateIntake:
    candidate: CandidateDirection
    validation: CandidateValidationResult

    @property
    def is_valid(self) -> bool:
        return self.validation.is_valid


def intake_regenerated_candidate(
    payload: Any,
    brief: EvidenceBrief,
) -> RegeneratedCandidateIntake:
    """
    Parse and validate one regeneration response against the original brief.

    This function does not call an LLM, score candidates, or mutate planning
    state. It is the safe entry point for a future targeted retry response.
    """
    candidate = parse_single_candidate_payload(payload)
    validation = validate_candidate(candidate, brief)

    return RegeneratedCandidateIntake(
        candidate=candidate,
        validation=validation,
    )
