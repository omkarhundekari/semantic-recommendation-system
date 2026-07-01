import json
from typing import Dict

from planning.planner_models import EvidenceBrief
from planning.candidate_models import CandidateGenerationRequest


def build_candidate_generation_payload(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
) -> Dict:
    return {
        "task": (
            "Generate exactly three distinct, buildable software project "
            "directions from the evidence brief."
        ),
        "rules": [
            "Use only source IDs that exist in the evidence brief.",
            "Cite only sources directly material to that candidate; do not cite every available source by default.",
            "Treat sources marked support_scope=adjacent_planning as optional planning context, not core evidence support.",
            "Do not claim direct research support unless a cited source is a research paper.",
            "Do not invent papers, repositories, datasets, benchmarks, or source facts.",
            "Keep each MVP achievable for the user's stated timeline and skill level.",
            "Treat the user's stated goal as the primary scope; do not narrow into a language, region, industry, or specialist audience unless the user explicitly asks for it.",
            "For timelines of three weeks or less, keep each direction centered on one primary technical differentiator and avoid combining several advanced subsystems into one MVP.",
            "When evidence is niche but the user request is broad, use that evidence as an optional extension rather than making it the central project direction.",
            "Make all three directions materially different in user workflow or technical focus.",
            "Return structured JSON only.",
        ],
        "user_request": request.to_dict(),
        "evidence_brief": brief.to_dict(),
        "required_schema": {
            "candidates": [
                {
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
            ]
        },
    }


def build_candidate_generation_prompt(
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
) -> str:
    payload = build_candidate_generation_payload(
        brief=brief,
        request=request,
    )

    return json.dumps(payload, indent=2, ensure_ascii=False)
