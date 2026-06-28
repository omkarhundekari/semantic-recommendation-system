from typing import Any

from planning.generation_provider import CandidateGenerationProvider


class MockCandidateGenerationProvider(CandidateGenerationProvider):
    def __init__(self, response: Any):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> Any:
        self.prompts.append(prompt)
        return self.response
