import hashlib
from dataclasses import dataclass
from typing import List

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
    CandidateValidationResult,
)
from planning.candidate_parser import parse_candidate_payload
from planning.candidate_prompt import build_candidate_generation_prompt
from planning.candidate_validator import validate_candidate_set
from planning.generation_provider import CandidateGenerationProvider
from planning.planner_models import EvidenceBrief


@dataclass
class CandidateGenerationOutcome:
    candidates: List[CandidateDirection]
    validations: List[CandidateValidationResult]
    provider_called: bool
    prompt_content_hash: str = ""

    @property
    def valid_candidates(self) -> List[CandidateDirection]:
        return [
            candidate
            for candidate, validation in zip(
                self.candidates,
                self.validations,
            )
            if validation.is_valid
        ]


def generate_validated_candidates(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    provider: CandidateGenerationProvider,
) -> CandidateGenerationOutcome:
    prompt = build_candidate_generation_prompt(
        brief=brief,
        request=request,
    )
    prompt_content_hash = hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()

    raw_response = provider.generate(prompt)
    candidates = parse_candidate_payload(raw_response)
    validations = validate_candidate_set(
        candidates=candidates,
        brief=brief,
    )

    return CandidateGenerationOutcome(
        candidates=candidates,
        validations=validations,
        provider_called=True,
        prompt_content_hash=prompt_content_hash,
    )
