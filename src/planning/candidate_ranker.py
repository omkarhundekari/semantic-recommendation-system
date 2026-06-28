import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.planner_models import EvidenceBrief


@dataclass
class RankedCandidate:
    candidate: CandidateDirection
    score: float
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


def _tokens(value: str) -> set:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", str(value).lower())
        if token not in {
            "and",
            "for",
            "from",
            "into",
            "with",
            "this",
            "that",
            "build",
            "project",
            "system",
        }
    }


def _candidate_text(candidate: CandidateDirection) -> str:
    """Return complete candidate text for constraint-alignment scoring."""
    return " ".join(
        [
            candidate.title,
            candidate.problem_statement,
            candidate.target_user,
            " ".join(candidate.core_workflow),
            " ".join(candidate.mvp_scope),
            " ".join(candidate.success_metrics),
            candidate.evidence_relationship,
            " ".join(candidate.suggested_stack),
        ]
    )


def _diversity_text(candidate: CandidateDirection) -> str:
    """Return workflow-defining text used only for diversity checks."""
    return " ".join(
        [
            candidate.title,
            " ".join(candidate.core_workflow),
            " ".join(candidate.mvp_scope),
        ]
    )


def _time_budget_days(value: str) -> int:
    text = str(value or "").lower().strip()

    if not text:
        return 0

    if "weekend" in text:
        return 2

    match = re.search(r"(\d+)\s*(day|days|week|weeks|month|months)", text)

    if not match:
        return 0

    amount = int(match.group(1))
    unit = match.group(2)

    if "week" in unit:
        return amount * 7

    if "month" in unit:
        return amount * 30

    return amount


def _evidence_score(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
) -> float:
    known_source_ids = {source.source_id for source in brief.sources}

    if not candidate.source_ids:
        return 0.55

    matched = [
        source_id
        for source_id in candidate.source_ids
        if source_id in known_source_ids
    ]

    if not matched:
        return 0.0

    coverage = len(set(matched)) / max(1, len(candidate.source_ids))
    breadth = min(1.0, len(set(matched)) / 2)

    return round((coverage * 0.75) + (breadth * 0.25), 3)


def _feasibility_score(
    candidate: CandidateDirection,
    request: CandidateGenerationRequest,
) -> float:
    budget_days = _time_budget_days(request.time_available)
    mvp_steps = len(candidate.mvp_scope)
    workflow_steps = len(candidate.core_workflow)

    score = 1.0

    if budget_days and budget_days <= 7 and mvp_steps > 4:
        score -= 0.35
    elif budget_days and budget_days <= 21 and mvp_steps > 6:
        score -= 0.2
    elif mvp_steps > 7:
        score -= 0.25

    if workflow_steps > 5:
        score -= 0.1

    if len(candidate.suggested_stack) > 7:
        score -= 0.1

    return round(max(0.0, score), 3)


def _constraint_alignment_score(
    candidate: CandidateDirection,
    request: CandidateGenerationRequest,
) -> float:
    requested_stack = _tokens(" ".join(request.preferred_stack))
    requested_roles = _tokens(" ".join(request.target_roles))
    candidate_tokens = _tokens(_candidate_text(candidate))

    stack_overlap = (
        len(requested_stack & candidate_tokens) / len(requested_stack)
        if requested_stack
        else 1.0
    )
    role_overlap = (
        len(requested_roles & candidate_tokens) / len(requested_roles)
        if requested_roles
        else 1.0
    )

    return round((stack_overlap * 0.55) + (role_overlap * 0.45), 3)


def _clarity_score(candidate: CandidateDirection) -> float:
    sections = [
        candidate.title,
        candidate.problem_statement,
        candidate.target_user,
        candidate.core_workflow,
        candidate.mvp_scope,
        candidate.success_metrics,
        candidate.evidence_relationship,
    ]

    completed = sum(bool(section) for section in sections)
    return round(completed / len(sections), 3)


def _jaccard_similarity(left_tokens: set, right_tokens: set) -> float:
    if not left_tokens or not right_tokens:
        return 0.0

    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _title_similarity(
    left: CandidateDirection,
    right: CandidateDirection,
) -> float:
    return _jaccard_similarity(
        _tokens(left.title),
        _tokens(right.title),
    )


def _similarity(
    left: CandidateDirection,
    right: CandidateDirection,
) -> float:
    return _jaccard_similarity(
        _tokens(_diversity_text(left)),
        _tokens(_diversity_text(right)),
    )


def _is_near_duplicate(
    left: CandidateDirection,
    right: CandidateDirection,
    workflow_similarity_threshold: float,
    title_similarity_threshold: float,
) -> bool:
    return (
        _title_similarity(left, right) >= title_similarity_threshold
        or _similarity(left, right) >= workflow_similarity_threshold
    )


def rank_candidates(
    candidates: Sequence[CandidateDirection],
    brief: EvidenceBrief,
    request: CandidateGenerationRequest,
) -> List[RankedCandidate]:
    ranked = []

    for candidate in candidates:
        evidence = _evidence_score(candidate, brief)
        feasibility = _feasibility_score(candidate, request)
        alignment = _constraint_alignment_score(candidate, request)
        clarity = _clarity_score(candidate)

        score = (
            (evidence * 0.35)
            + (feasibility * 0.30)
            + (alignment * 0.20)
            + (clarity * 0.15)
        )

        reasons = [
            f"Evidence support score: {evidence:.2f}.",
            f"Feasibility score: {feasibility:.2f}.",
            f"Constraint alignment score: {alignment:.2f}.",
            f"Completeness score: {clarity:.2f}.",
        ]

        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=round(score, 3),
                score_breakdown={
                    "evidence_support": evidence,
                    "feasibility": feasibility,
                    "constraint_alignment": alignment,
                    "clarity": clarity,
                },
                reasons=reasons,
            )
        )

    return sorted(
        ranked,
        key=lambda item: item.score,
        reverse=True,
    )


def select_diverse_candidates(
    ranked_candidates: Sequence[RankedCandidate],
    max_candidates: int = 3,
    similarity_threshold: float = 0.62,
    title_similarity_threshold: float = 0.40,
) -> List[RankedCandidate]:
    selected = []

    for ranked in ranked_candidates:
        if len(selected) >= max_candidates:
            break

        is_duplicate = any(
            _is_near_duplicate(
                ranked.candidate,
                prior.candidate,
                workflow_similarity_threshold=similarity_threshold,
                title_similarity_threshold=title_similarity_threshold,
            )
            for prior in selected
        )

        if is_duplicate:
            continue

        selected.append(ranked)

    return selected
