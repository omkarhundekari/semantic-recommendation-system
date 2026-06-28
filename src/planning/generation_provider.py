from abc import ABC, abstractmethod
from typing import Any


class CandidateGenerationProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> Any:
        """Return JSON-compatible candidate-generation output."""
        raise NotImplementedError
