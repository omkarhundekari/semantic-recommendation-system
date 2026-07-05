import json
from typing import Any, Dict, Optional, Sequence

from planning.candidate_models import CandidateDirection

from planning.candidate_models import CandidateGenerationRequest
from planning.planner_models import EvidenceBrief
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)


REGENERATION_PROMPT_VERSION = "v1"


def build_candidate_regeneration_payload(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    directive: DiversificationRepairDirective,
    surviving_candidates: Optional[
        Sequence[CandidateDirection]
    ] = None,
) -> Dict[str, Any]:
    regeneration_brief = directive.regeneration_brief
    surviving_candidates = list(surviving_candidates or [])

    survivor_exclusions = [
        {
            "title": candidate.title,
            "core_workflow": list(candidate.core_workflow),
            "mvp_scope": list(candidate.mvp_scope),
        }
        for candidate in surviving_candidates
    ]

    return {
        "task": (
            "Generate exactly one replacement software project direction "
            "for a semantically overlapping candidate."
        ),
        "rules": [
            "Return exactly one candidate object.",
            "Use only source IDs that exist in the evidence brief.",
            (
                "Preserve the user's original goal, constraints, and "
                "evidence-grounding requirements."
            ),
            (
                "Do not repeat any surviving candidate's primary workflow, "
                "MVP focus, or system boundary."
            ),
            (
                "The replacement must be materially distinct in technical "
                "workflow, target-user interaction, or system boundary."
            ),
            (
                "Do not invent papers, repositories, datasets, benchmarks, "
                "or source facts."
            ),
            (
                "Keep the MVP achievable for the stated timeline and "
                "skill level."
            ),
            "Return structured JSON only.",
        ],
        "user_request": request.to_dict(),
        "evidence_brief": brief.to_dict(),
        "surviving_candidates_to_avoid": survivor_exclusions,
        "repair_directive": {
            "replace_candidate_title": (
                directive.replace_candidate_title
            ),
            "retain_candidate_titles": list(
                directive.retain_candidate_titles
            ),
            "highest_pair_similarity": (
                directive.highest_pair_similarity
            ),
            "reason": directive.reason,
            "regeneration_brief": regeneration_brief,
        },
        "required_schema": {
            "candidate": {
                "title": "string",
                "problem_statement": "string",
                "target_user": "string",
                "core_workflow": ["string"],
                "mvp_scope": ["string"],
                "success_metrics": ["string"],
                "evidence_relationship": "string",
                "source_ids": ["string"],
                "assumptions": ["string"],
                "suggested_stack": ["string"],
            }
        },
    }


def build_candidate_regeneration_prompt(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
    directive: DiversificationRepairDirective,
    surviving_candidates: Optional[
        Sequence[CandidateDirection]
    ] = None,
) -> str:
    payload = build_candidate_regeneration_payload(
        brief=brief,
        request=request,
        directive=directive,
        surviving_candidates=surviving_candidates,
    )

    return json.dumps(payload, indent=2, ensure_ascii=False)
