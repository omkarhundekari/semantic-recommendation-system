import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

from planning.generation_provider import CandidateGenerationProvider
from planning.live_llm_guard import require_live_openai_access


load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[2] / ".env",
    override=False,
)


CANDIDATE_OBJECT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "problem_statement": {"type": "string"},
        "target_user": {"type": "string"},
        "core_workflow": {
            "type": "array",
            "minItems": 2,
            "items": {"type": "string"},
        },
        "mvp_scope": {
            "type": "array",
            "minItems": 3,
            "maxItems": 7,
            "items": {"type": "string"},
        },
        "success_metrics": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string"},
        },
        "evidence_relationship": {"type": "string"},
        "source_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "assumptions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "suggested_stack": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "title",
        "problem_statement",
        "target_user",
        "core_workflow",
        "mvp_scope",
        "success_metrics",
        "evidence_relationship",
        "source_ids",
        "assumptions",
        "suggested_stack",
    ],
}


CANDIDATE_GENERATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidates": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": CANDIDATE_OBJECT_SCHEMA,
        }
    },
    "required": ["candidates"],
}


CANDIDATE_REGENERATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "candidate": CANDIDATE_OBJECT_SCHEMA,
    },
    "required": ["candidate"],
}


class OpenAICandidateGenerationProvider(CandidateGenerationProvider):
    def __init__(
        self,
        model: Optional[str] = None,
        max_output_tokens: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
        client: Optional[OpenAI] = None,
    ):
        self.model = model or os.getenv("OPENAI_MODEL", "").strip()
        self.max_output_tokens = int(
            max_output_tokens
            or os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2500")
        )
        self.timeout_seconds = float(
            timeout_seconds
            or os.getenv("LLM_TIMEOUT_SECONDS", "35")
        )
        self.last_usage: Dict[str, Optional[int]] = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }

        if client is not None:
            self.client = client
            return

        api_key = os.getenv("OPENAI_API_KEY", "").strip()

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required for the OpenAI provider."
            )

        if not self.model:
            raise RuntimeError(
                "OPENAI_MODEL must be set before using the OpenAI provider."
            )

        self.client = OpenAI(
            api_key=api_key,
            max_retries=0,
            timeout=self.timeout_seconds,
        )

    def _generate_structured_json(
        self,
        prompt: str,
        schema_name: str,
        schema: Dict[str, Any],
        empty_output_message: str,
    ) -> Any:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            max_output_tokens=self.max_output_tokens,
            store=False,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )

        usage = getattr(response, "usage", None)
        self.last_usage = {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

        output_text = getattr(response, "output_text", "")

        if not output_text:
            raise RuntimeError(empty_output_message)

        try:
            return json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "OpenAI returned output that was not valid JSON."
            ) from exc

    def generate(self, prompt: str) -> Any:
        return self._generate_structured_json(
            prompt=prompt,
            schema_name="candidate_generation",
            schema=CANDIDATE_GENERATION_SCHEMA,
            empty_output_message=(
                "OpenAI returned no structured candidate-generation output."
            ),
        )

    def generate_regeneration(
        self,
        prompt: str,
        allow_live_llm: bool = False,
    ) -> Any:
        require_live_openai_access(
            provider_name="openai",
            allow_live_llm=allow_live_llm,
        )

        return self._generate_structured_json(
            prompt=prompt,
            schema_name="candidate_regeneration",
            schema=CANDIDATE_REGENERATION_SCHEMA,
            empty_output_message=(
                "OpenAI returned no structured candidate-regeneration output."
            ),
        )
