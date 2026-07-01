import hashlib
import math
from dataclasses import dataclass
from typing import Protocol, Sequence, Tuple

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)


@dataclass(frozen=True)
class EmbeddingVector:
    values: Tuple[float, ...]

    def cosine_similarity(self, other: "EmbeddingVector") -> float:
        dot_product = sum(
            left * right
            for left, right in zip(self.values, other.values)
        )
        left_norm = math.sqrt(sum(value ** 2 for value in self.values))
        right_norm = math.sqrt(sum(value ** 2 for value in other.values))

        if not left_norm or not right_norm:
            return 0.0

        return dot_product / (left_norm * right_norm)


class TextEncoder(Protocol):
    def encode_text(self, text: str) -> EmbeddingVector:
        ...


@dataclass(frozen=True)
class GoalRelevanceTrace:
    candidate_key: str
    candidate_title: str
    raw_cosine: float
    normalized_score: float
    goal_text_used: str
    candidate_text_used: str

    def to_dict(self) -> dict:
        return {
            "candidate_key": self.candidate_key,
            "candidate_title": self.candidate_title,
            "raw_cosine": round(self.raw_cosine, 4),
            "normalized_score": round(self.normalized_score, 4),
            "goal_text_used": self.goal_text_used,
            "candidate_text_used": self.candidate_text_used,
        }


@dataclass(frozen=True)
class GoalRelevanceResult:
    candidate_key: str
    score: float
    trace: GoalRelevanceTrace


def _candidate_key(candidate: CandidateDirection) -> str:
    raw_value = (
        f"{candidate.title}::{candidate.problem_statement}"
    )
    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()[:12]


def _build_goal_text(
    request: CandidateGenerationRequest,
) -> str:
    parts = [request.user_goal.strip()]

    if request.target_roles:
        parts.append(
            "Target roles: "
            + ", ".join(request.target_roles)
            + "."
        )

    return " ".join(part for part in parts if part)


def _build_candidate_text(
    candidate: CandidateDirection,
) -> str:
    parts = [
        candidate.title.strip().rstrip("."),
        candidate.problem_statement.strip().rstrip("."),
        candidate.target_user.strip().rstrip("."),
    ]
    return ". ".join(part for part in parts if part)


def _normalize_cosine(raw_cosine: float) -> float:
    return max(0.0, min(1.0, (raw_cosine + 1.0) / 2.0))


class GoalRelevanceScorer:
    def __init__(self, encoder: TextEncoder):
        self._encoder = encoder

    def score_candidates(
        self,
        request: CandidateGenerationRequest,
        candidates: Sequence[CandidateDirection],
    ) -> list:
        if not candidates:
            return []

        goal_text = _build_goal_text(request)
        goal_embedding = self._encoder.encode_text(goal_text)
        results = []

        for candidate in candidates:
            candidate_text = _build_candidate_text(candidate)
            candidate_embedding = self._encoder.encode_text(
                candidate_text
            )
            raw_cosine = goal_embedding.cosine_similarity(
                candidate_embedding
            )
            normalized_score = _normalize_cosine(raw_cosine)
            candidate_key = _candidate_key(candidate)

            trace = GoalRelevanceTrace(
                candidate_key=candidate_key,
                candidate_title=candidate.title,
                raw_cosine=raw_cosine,
                normalized_score=normalized_score,
                goal_text_used=goal_text,
                candidate_text_used=candidate_text,
            )

            results.append(
                GoalRelevanceResult(
                    candidate_key=candidate_key,
                    score=normalized_score,
                    trace=trace,
                )
            )

        return results
