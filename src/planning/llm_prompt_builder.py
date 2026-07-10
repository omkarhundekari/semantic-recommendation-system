from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from planning.evidence_cards import EvidenceCard


DEFAULT_PROMPT_VERSION = "evidence_card_prompt_v1"

SYSTEM_INSTRUCTION = (
    "You are a grounded project synthesis assistant. Generate concise project "
    "directions using only the provided evidence cards. Return valid JSON only. "
    "Do not include markdown, prose outside JSON, or trailing commentary. Do not "
    "invent sources, datasets, benchmarks, or claims. Preserve uncertainty when "
    "evidence is limited, exploratory, adjacent, or implementation-only. Cite "
    "only source IDs that appear in the evidence cards."
)

OUTPUT_SCHEMA = {
    "project_directions": [
        {
            "title": "string",
            "problem_statement": "string",
            "target_user": "string",
            "why_this_is_grounded": "string",
            "source_ids": ["string"],
            "evidence_confidence": "Strong | Limited | Exploratory",
            "grounding_warnings": ["string"],
            "mvp_scope": ["string"],
            "advanced_extensions": ["string"],
            "skills_demonstrated": ["string"],
            "resume_bullet": "string",
            "interview_talking_points": ["string"],
        }
    ],
    "overall_confidence": "Strong | Limited | Exploratory",
    "assumptions": ["string"],
    "warnings": ["string"],
}


@dataclass(frozen=True)
class LLMSynthesisPrompt:
    prompt_version: str
    system_instruction: str
    user_goal: str
    constraints: dict[str, Any]
    evidence_cards: list[dict[str, Any]]
    output_schema: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
        )


def build_llm_synthesis_prompt(
    *,
    user_goal: str,
    constraints: dict[str, Any],
    evidence_cards: list[Any],
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    system_instruction: str = SYSTEM_INSTRUCTION,
    output_schema: dict[str, Any] | None = None,
) -> LLMSynthesisPrompt:
    return LLMSynthesisPrompt(
        prompt_version=prompt_version,
        system_instruction=system_instruction,
        user_goal=user_goal,
        constraints=constraints,
        evidence_cards=[
            _card_to_prompt_payload(card)
            for card in evidence_cards
        ],
        output_schema=output_schema or OUTPUT_SCHEMA,
    )


def render_llm_synthesis_prompt_text(
    prompt: LLMSynthesisPrompt,
) -> str:
    return "\n".join(
        [
            "# System Instruction",
            prompt.system_instruction,
            "",
            "# User Goal",
            prompt.user_goal,
            "",
            "# Constraints",
            json.dumps(prompt.constraints, indent=2, sort_keys=True),
            "",
            "# Evidence Cards",
            json.dumps(prompt.evidence_cards, indent=2, sort_keys=True),
            "",
            "# Required Output Schema",
            json.dumps(prompt.output_schema, indent=2, sort_keys=True),
            "",
            "# Rules",
            "- Return valid JSON only.",
            "- Return exactly one strongest project direction unless the user explicitly asks for more.",
            "- Use only source IDs present in the evidence cards.",
            "- Preserve grounding warnings in the output.",
            "- Do not upgrade Limited or Exploratory evidence to Strong.",
            "- Keep each list concise: 3 to 5 items maximum.",
            "- If evidence is weak, say what is missing instead of pretending confidence.",
        ]
    )


def _card_to_prompt_payload(card: Any) -> dict[str, Any]:
    if isinstance(card, EvidenceCard):
        raw = card.to_dict()
    elif isinstance(card, dict):
        raw = card
    elif hasattr(card, "to_dict"):
        raw = card.to_dict()
    else:
        raw = asdict(card)

    allowed_fields = [
        "source_id",
        "source_type",
        "title",
        "support_scope",
        "evidence_confidence",
        "key_excerpt",
        "specific_method_or_technique",
        "specific_dataset_or_benchmark",
        "specific_implementation_signal",
        "grounding_warning",
        "relevance_signal",
        "user_facing_explanation",
    ]

    return {
        field: raw.get(field)
        for field in allowed_fields
        if raw.get(field) not in (None, "", [], ())
    }
