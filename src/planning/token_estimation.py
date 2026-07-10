from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any


DEFAULT_CHARS_PER_TOKEN = 4
DEFAULT_SAFETY_MULTIPLIER = 1.15


@dataclass(frozen=True)
class TokenEstimate:
    estimated_tokens: int
    raw_character_count: int
    chars_per_token: int
    safety_multiplier: float
    section_token_estimates: dict[str, int]
    largest_sections: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_tokens_for_text(
    text: str,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
) -> int:
    if chars_per_token <= 0:
        raise ValueError("chars_per_token must be positive.")
    if safety_multiplier <= 0:
        raise ValueError("safety_multiplier must be positive.")

    raw_estimate = len(text) / chars_per_token
    return math.ceil(raw_estimate * safety_multiplier)


def estimate_tokens_for_sections(
    sections: dict[str, Any],
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
    largest_section_count: int = 3,
) -> TokenEstimate:
    if largest_section_count <= 0:
        raise ValueError("largest_section_count must be positive.")

    serialized_sections = {
        name: _serialize_section(value)
        for name, value in sections.items()
    }

    section_token_estimates = {
        name: estimate_tokens_for_text(
            value,
            chars_per_token=chars_per_token,
            safety_multiplier=safety_multiplier,
        )
        for name, value in serialized_sections.items()
    }

    raw_character_count = sum(
        len(value) for value in serialized_sections.values()
    )
    estimated_tokens = sum(section_token_estimates.values())

    largest_sections = tuple(
        name
        for name, _ in sorted(
            section_token_estimates.items(),
            key=lambda item: (-item[1], item[0]),
        )[:largest_section_count]
    )

    return TokenEstimate(
        estimated_tokens=estimated_tokens,
        raw_character_count=raw_character_count,
        chars_per_token=chars_per_token,
        safety_multiplier=safety_multiplier,
        section_token_estimates=section_token_estimates,
        largest_sections=largest_sections,
    )


def estimate_tokens_for_prompt(
    prompt: Any,
    *,
    chars_per_token: int = DEFAULT_CHARS_PER_TOKEN,
    safety_multiplier: float = DEFAULT_SAFETY_MULTIPLIER,
) -> TokenEstimate:
    if hasattr(prompt, "to_dict"):
        prompt_payload = prompt.to_dict()
    else:
        prompt_payload = prompt

    if not isinstance(prompt_payload, dict):
        raise TypeError("prompt must be a dictionary or expose to_dict().")

    return estimate_tokens_for_sections(
        prompt_payload,
        chars_per_token=chars_per_token,
        safety_multiplier=safety_multiplier,
    )


def estimate_llm_synthesis_prompt_tokens(
    *,
    user_goal: str,
    constraints: dict[str, Any],
    evidence_cards: list[Any],
    mode: str,
    system_instruction: str,
    output_schema: dict[str, Any],
) -> TokenEstimate:
    sections = {
        "system_instruction": system_instruction,
        "user_goal": user_goal,
        "constraints": constraints,
        "mode": mode,
        "evidence_cards": [
            _card_to_prompt_dict(card)
            for card in evidence_cards
        ],
        "output_schema": output_schema,
    }
    return estimate_tokens_for_sections(sections)


def is_within_token_budget(
    estimate: TokenEstimate,
    token_budget: int,
) -> bool:
    if token_budget < 0:
        raise ValueError("token_budget must be non-negative.")
    return estimate.estimated_tokens <= token_budget


def _serialize_section(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _card_to_prompt_dict(card: Any) -> dict[str, Any]:
    if isinstance(card, dict):
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
