from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from planning.llm_prompt_builder import render_llm_synthesis_prompt_text
from planning.llm_synthesis_client import LLMSynthesisRequest


DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"


class OpenAIProviderConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OpenAISynthesisProvider:
    configured_model_name: str | None = None
    provider_name: str = "openai"
    api_key_env_var: str = "OPENAI_API_KEY"
    temperature: float = 0.2
    max_output_tokens: int = 1200
    client: Any | None = None

    def synthesize(
        self,
        request: LLMSynthesisRequest,
    ) -> str:
        client = self.client or self._build_client()
        prompt_text = render_llm_synthesis_prompt_text(request.prompt)

        response = client.responses.create(
            model=self.resolved_model_name,
            input=[
                {
                    "role": "system",
                    "content": request.prompt.system_instruction,
                },
                {
                    "role": "user",
                    "content": prompt_text,
                },
            ],
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

        return _extract_response_text(response)

    @property
    def model_name(self) -> str:
        return self.configured_model_name or os.getenv(
            "OPENAI_MODEL",
            DEFAULT_OPENAI_MODEL,
        )

    @property
    def resolved_model_name(self) -> str:
        return self.model_name

    def _build_client(self) -> Any:
        api_key = os.getenv(self.api_key_env_var)
        if not api_key:
            raise OpenAIProviderConfigurationError(
                f"{self.api_key_env_var} is not set."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIProviderConfigurationError(
                "openai package is not installed."
            ) from exc

        return OpenAI(api_key=api_key)


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    if isinstance(response, dict):
        output_text = response.get("output_text")
        if output_text:
            return str(output_text)

    try:
        chunks = []
        for item in response.output:
            for content in item.content:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks)
    except Exception:
        pass

    raise ValueError("Could not extract text from OpenAI response.")
