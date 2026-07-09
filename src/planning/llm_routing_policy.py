from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


ROUTING_APPROVED = "routing_approved"
NO_EVIDENCE_CARDS = "no_evidence_cards"
NO_QUERY_ALIGNED_EVIDENCE = "no_query_aligned_evidence"
EXPLORATORY_EVIDENCE_ONLY = "exploratory_evidence_only"
DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE = "deterministic_sufficient_for_fast_mode"
QUOTA_EXHAUSTED = "quota_exhausted"
TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
BUDGET_UNAVAILABLE = "budget_unavailable"

FAST_MODE = "fast"
DEEP_MODE = "deep"
INTERVIEW_MODE = "interview"

STRONG_CONFIDENCE = "Strong"
LIMITED_CONFIDENCE = "Limited"
EXPLORATORY_CONFIDENCE = "Exploratory"

PLAUSIBLE_RELEVANCE = "plausible"
WEAK_RELEVANCE = "weak"
SUSPICIOUS_RELEVANCE = "suspicious"


@dataclass(frozen=True)
class SessionBudgetState:
    calls_remaining: int
    tokens_remaining: int | None
    budget_available: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LLMRoutingDecision:
    should_route: bool
    reason: str
    mode: str
    evidence_confidence: str | None
    query_aligned_card_count: int
    weak_card_count: int
    suspicious_card_count: int
    estimated_tokens: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_llm_routing(
    *,
    evidence_cards: list[Any],
    session_budget: SessionBudgetState,
    mode: str,
    estimated_tokens: int | None = None,
) -> LLMRoutingDecision:
    evidence_confidence = _infer_evidence_confidence(evidence_cards)
    query_aligned_card_count = _count_query_aligned_cards(evidence_cards)
    weak_card_count = _count_cards_by_relevance(evidence_cards, WEAK_RELEVANCE)
    suspicious_card_count = _count_cards_by_relevance(
        evidence_cards,
        SUSPICIOUS_RELEVANCE,
    )

    base_decision = {
        "mode": mode,
        "evidence_confidence": evidence_confidence,
        "query_aligned_card_count": query_aligned_card_count,
        "weak_card_count": weak_card_count,
        "suspicious_card_count": suspicious_card_count,
        "estimated_tokens": estimated_tokens,
    }

    if not evidence_cards:
        return LLMRoutingDecision(
            should_route=False,
            reason=NO_EVIDENCE_CARDS,
            **base_decision,
        )

    if query_aligned_card_count == 0:
        return LLMRoutingDecision(
            should_route=False,
            reason=NO_QUERY_ALIGNED_EVIDENCE,
            **base_decision,
        )

    if evidence_confidence == EXPLORATORY_CONFIDENCE:
        return LLMRoutingDecision(
            should_route=False,
            reason=EXPLORATORY_EVIDENCE_ONLY,
            **base_decision,
        )

    if (
        mode == FAST_MODE
        and evidence_confidence == STRONG_CONFIDENCE
        and query_aligned_card_count >= 3
        and suspicious_card_count == 0
        and weak_card_count == 0
    ):
        return LLMRoutingDecision(
            should_route=False,
            reason=DETERMINISTIC_SUFFICIENT_FOR_FAST_MODE,
            **base_decision,
        )

    if not session_budget.budget_available:
        return LLMRoutingDecision(
            should_route=False,
            reason=BUDGET_UNAVAILABLE,
            **base_decision,
        )

    if session_budget.calls_remaining <= 0:
        return LLMRoutingDecision(
            should_route=False,
            reason=QUOTA_EXHAUSTED,
            **base_decision,
        )

    if (
        estimated_tokens is not None
        and session_budget.tokens_remaining is not None
        and estimated_tokens > session_budget.tokens_remaining
    ):
        return LLMRoutingDecision(
            should_route=False,
            reason=TOKEN_BUDGET_EXCEEDED,
            **base_decision,
        )

    return LLMRoutingDecision(
        should_route=True,
        reason=ROUTING_APPROVED,
        **base_decision,
    )


def _infer_evidence_confidence(evidence_cards: list[Any]) -> str | None:
    if not evidence_cards:
        return None

    confidences = {
        _get_card_value(card, "evidence_confidence")
        for card in evidence_cards
    }

    if confidences == {STRONG_CONFIDENCE}:
        return STRONG_CONFIDENCE

    if confidences == {EXPLORATORY_CONFIDENCE}:
        return EXPLORATORY_CONFIDENCE

    return LIMITED_CONFIDENCE


def _count_query_aligned_cards(evidence_cards: list[Any]) -> int:
    return sum(
        1
        for card in evidence_cards
        if _get_card_value(card, "support_scope") == "direct"
        and _get_card_value(card, "relevance_signal") == PLAUSIBLE_RELEVANCE
    )


def _count_cards_by_relevance(evidence_cards: list[Any], relevance: str) -> int:
    return sum(
        1
        for card in evidence_cards
        if _get_card_value(card, "relevance_signal") == relevance
    )


def _get_card_value(card: Any, field_name: str) -> Any:
    if isinstance(card, dict):
        return card.get(field_name)
    return getattr(card, field_name)
