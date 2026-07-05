from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PlanningSource(str, Enum):
    DETERMINISTIC = "deterministic"
    OPENAI = "openai"
    OPENAI_REPAIRED = "openai_repaired"
    OPENAI_FALLBACK = "openai_fallback"


class RegenerationRejectionReason(str, Enum):
    PARSE_FAILURE = "parse_failure"
    VALIDATION_FAILURE = "validation_failure"
    GROUNDING_FAILURE = "grounding_failure"
    DIVERSITY_FAILURE = "diversity_failure"
    PROMOTION_FAILURE = "promotion_failure"
    FEASIBILITY_FAILURE = "feasibility_failure"


class RegenerationAttemptRecord(BaseModel):
    """
    One rejected generation or regeneration attempt preceding the accepted
    candidate represented by CandidateProvenance.
    """

    attempt_number: int = Field(ge=1)
    rejection_reason: RegenerationRejectionReason
    candidate_title: Optional[str] = None
    grounding_adequacy: Optional[str] = None
    diversity_similarity_score: Optional[float] = None
    promotion_status: Optional[str] = None


class CandidateProvenance(BaseModel):
    """
    Planning-history metadata for a candidate entering deterministic
    product enrichment.
    """

    planning_source: PlanningSource
    prompt_version: Optional[str] = None
    generation_attempt: int = Field(default=1, ge=1)
    replacement_angle: Optional[str] = None
    rejected_alternatives: int = Field(default=0, ge=0)
    regeneration_attempts: List[RegenerationAttemptRecord] = Field(
        default_factory=list
    )
    grounding_adequacy: Optional[str] = None
    diversity_check_passed: Optional[bool] = None
    promotion_eligible: Optional[bool] = None

    def validate_history(self) -> None:
        attempt_numbers = [
            record.attempt_number
            for record in self.regeneration_attempts
        ]

        if len(attempt_numbers) != len(set(attempt_numbers)):
            raise ValueError(
                "Regeneration attempt records must use unique attempt numbers."
            )

        if self.regeneration_attempts and (
            self.rejected_alternatives
            != len(self.regeneration_attempts)
        ):
            raise ValueError(
                "rejected_alternatives must match the number of structured "
                "regeneration attempt records."
            )

        if any(
            attempt_number >= self.generation_attempt
            for attempt_number in attempt_numbers
        ):
            raise ValueError(
                "Rejected regeneration attempts must occur before the "
                "accepted generation_attempt."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate_history()

        if hasattr(self, "model_dump"):
            return self.model_dump(exclude_none=True)

        return self.dict(exclude_none=True)
