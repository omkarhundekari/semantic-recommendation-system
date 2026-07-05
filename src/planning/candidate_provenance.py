from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class CandidateProvenance(BaseModel):
    """
    Immutable planning-history metadata for a candidate that may later enter
    the deterministic product-enrichment pipeline.
    """

    planning_source: Literal[
        "deterministic",
        "openai",
        "openai_repaired",
    ]
    prompt_version: Optional[str] = None
    generation_attempt: int = Field(default=1, ge=1)
    replacement_angle: Optional[str] = None
    rejected_alternatives: int = Field(default=0, ge=0)
    grounding_adequacy: Optional[str] = None
    diversity_check_passed: Optional[bool] = None
    promotion_eligible: Optional[bool] = None

    def to_dict(self) -> Dict[str, object]:
        if hasattr(self, "model_dump"):
            return self.model_dump(exclude_none=True)

        return self.dict(exclude_none=True)
