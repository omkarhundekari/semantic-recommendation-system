from dataclasses import asdict, dataclass
from typing import Any, Dict, Sequence

from planning.candidate_models import CandidateDirection, CandidateGenerationRequest
from planning.candidate_regeneration_intake import (
    RegeneratedCandidateIntake,
    intake_regenerated_candidate,
)
from planning.candidate_regeneration_prompt import (
    build_candidate_regeneration_prompt,
)
from planning.candidate_replacement_evaluator import (
    CandidateReplacementEvaluation,
    evaluate_regenerated_candidate,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.planner_models import EvidenceBrief
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)


@dataclass(frozen=True)
class CandidateRegenerationCycle:
    prompt: str
    intake: RegeneratedCandidateIntake
    replacement_evaluation: CandidateReplacementEvaluation

    @property
    def accepted(self) -> bool:
        return self.replacement_evaluation.accepted_as_diverse_replacement

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "intake": {
                "candidate": self.intake.candidate.to_dict(),
                "validation": self.intake.validation.to_dict(),
                "is_valid": self.intake.is_valid,
            },
            "replacement_evaluation": (
                self.replacement_evaluation.to_dict()
            ),
            "accepted": self.accepted,
        }


def run_mock_regeneration_cycle(
    raw_response: Any,
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    directive: DiversificationRepairDirective,
    retained_candidates: Sequence[CandidateDirection],
    evidence_support_scorer: CandidateEvidenceSupportScorer,
    semantic_diversity_scorer: SemanticCandidateDiversityScorer,
) -> CandidateRegenerationCycle:
    """
    Run a complete targeted-regeneration evaluation without calling an LLM.

    `raw_response` represents a future provider response and is deliberately
    injected so this path is deterministic, testable, and free to run.
    """
    prompt = build_candidate_regeneration_prompt(
        brief=brief,
        request=request,
        directive=directive,
    )

    intake = intake_regenerated_candidate(
        payload=raw_response,
        brief=brief,
    )

    replacement_evaluation = evaluate_regenerated_candidate(
        candidate=intake.candidate,
        validation=intake.validation,
        retained_candidates=retained_candidates,
        brief=brief,
        evidence_support_scorer=evidence_support_scorer,
        semantic_diversity_scorer=semantic_diversity_scorer,
    )

    return CandidateRegenerationCycle(
        prompt=prompt,
        intake=intake,
        replacement_evaluation=replacement_evaluation,
    )
