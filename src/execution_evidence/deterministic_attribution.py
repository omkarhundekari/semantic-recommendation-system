from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Literal, Set

from pydantic import BaseModel, Field

from execution_evidence.models import (
    ExecutionEvidenceItem,
    RoadmapAttributionContext,
)
from planning.roadmap_snapshot import (
    RoadmapSnapshot,
    RoadmapStageSnapshot,
)


DETERMINISTIC_ATTRIBUTION_POLICY_VERSION = 2

MINIMUM_CANDIDATE_SCORE = 0.20
MINIMUM_TOP_MARGIN = 0.06
MINIMUM_MATCHED_TERMS = 2
MAX_MATCHED_TERMS_REPORTED = 12

CROSS_STAGE_MINIMUM_SCORE = 0.30
CROSS_STAGE_MINIMUM_DISTINCT_TERMS = 2

MAX_AUXILIARY_TO_LEXICAL_RATIO = 0.25

TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "with",
    "you",
    "your",
}

EXPLICIT_REVERT_TITLE_TERMS = {
    "revert",
    "reverted",
}

LOW_VALUE_TERMS = {
    "chore",
    "cleanup",
    "format",
    "formatting",
    "merge",
    "merged",
    "revert",
    "reverted",
    "typo",
    "wip",
}

STAGE_TYPE_PRIORS = {
    "release": {
        "package": 0.12,
        "validate": 0.04,
    },
    "workflow_run": {
        "validate": 0.12,
        "mvp": 0.04,
    },
    "pull_request": {
        "mvp": 0.08,
        "validate": 0.03,
    },
    "commit": {
        "mvp": 0.04,
    },
}


class AttributionSignal(BaseModel):
    name: str
    contribution: float
    detail: str


class DeterministicAttributionCandidate(BaseModel):
    roadmap_node_id: str = Field(min_length=1)
    roadmap_context: RoadmapAttributionContext
    score: float = Field(ge=0.0, le=1.0)
    content_score: float = Field(
        ge=0.0,
        le=1.0,
    )
    matched_terms: List[str] = Field(
        default_factory=list
    )
    content_matched_terms: List[str] = Field(
        default_factory=list
    )
    signals: List[AttributionSignal] = Field(
        default_factory=list
    )


class DeterministicAttributionSuggestion(BaseModel):
    evidence_key: str = Field(min_length=1)
    policy_version: int = (
        DETERMINISTIC_ATTRIBUTION_POLICY_VERSION
    )
    decision: Literal[
        "suggest",
        "abstain",
    ]
    abstention_reason: str = ""
    candidates: List[
        DeterministicAttributionCandidate
    ] = Field(default_factory=list)
    top_score: float = Field(ge=0.0, le=1.0)
    score_margin: float = Field(ge=0.0, le=1.0)


def suggest_deterministic_attribution(
    *,
    evidence: ExecutionEvidenceItem,
    roadmap: RoadmapSnapshot,
    top_k: int = 2,
) -> DeterministicAttributionSuggestion:
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    candidates = sorted(
        (
            _score_stage(
                evidence=evidence,
                roadmap=roadmap,
                stage=stage,
            )
            for stage in roadmap.stages
        ),
        key=lambda candidate: (
            -candidate.score,
            candidate.roadmap_node_id,
        ),
    )

    selected = candidates[:top_k]
    top_score = (
        selected[0].score
        if selected
        else 0.0
    )
    second_score = (
        selected[1].score
        if len(selected) > 1
        else 0.0
    )
    score_margin = round(
        max(0.0, top_score - second_score),
        6,
    )

    if _is_explicit_revert(evidence.title):
        decision = "abstain"
        abstention_reason = (
            "Explicitly reverted work does not count as "
            "positive roadmap progress."
        )
    elif _has_cross_stage_ambiguity(candidates):
        decision = "abstain"
        abstention_reason = (
            "The evidence contains distinct signals for "
            "multiple roadmap stages."
        )
    else:
        decision, abstention_reason = _decide(
            selected=selected,
            score_margin=score_margin,
        )

    return DeterministicAttributionSuggestion(
        evidence_key=evidence.evidence_key,
        decision=decision,
        abstention_reason=abstention_reason,
        candidates=selected,
        top_score=top_score,
        score_margin=score_margin,
    )


def _score_stage(
    *,
    evidence: ExecutionEvidenceItem,
    roadmap: RoadmapSnapshot,
    stage: RoadmapStageSnapshot,
) -> DeterministicAttributionCandidate:
    title_tokens = _tokenize(evidence.title)
    description_tokens = _tokenize(
        evidence.description
    )
    metadata_tokens = _metadata_tokens(
        evidence.metadata
    )
    stage_tokens = _stage_tokens(stage.content)

    title_matches = title_tokens & stage_tokens
    description_matches = (
        description_tokens & stage_tokens
    )
    metadata_matches = metadata_tokens & stage_tokens

    signals: List[AttributionSignal] = []

    title_score = _bounded_overlap(
        matched=title_matches,
        source=title_tokens,
        weight=0.58,
        cap_terms=6,
    )
    if title_score > 0:
        signals.append(
            AttributionSignal(
                name="title_overlap",
                contribution=title_score,
                detail=_match_detail(
                    "title",
                    title_matches,
                ),
            )
        )

    description_score = _bounded_overlap(
        matched=description_matches,
        source=description_tokens,
        weight=0.22,
        cap_terms=8,
    )
    if description_score > 0:
        signals.append(
            AttributionSignal(
                name="description_overlap",
                contribution=description_score,
                detail=_match_detail(
                    "description",
                    description_matches,
                ),
            )
        )

    raw_metadata_score = _bounded_overlap(
        matched=metadata_matches,
        source=metadata_tokens,
        weight=0.10,
        cap_terms=5,
    )

    raw_prior_score = (
        STAGE_TYPE_PRIORS
        .get(evidence.evidence_type, {})
        .get(stage.stage_id, 0.0)
    )

    lexical_score = (
        title_score
        + description_score
    )
    raw_auxiliary_score = (
        raw_metadata_score
        + raw_prior_score
    )
    auxiliary_cap = (
        lexical_score
        * MAX_AUXILIARY_TO_LEXICAL_RATIO
    )

    if raw_auxiliary_score > 0:
        auxiliary_scale = min(
            1.0,
            auxiliary_cap
            / raw_auxiliary_score,
        )
    else:
        auxiliary_scale = 0.0

    metadata_score = round(
        raw_metadata_score * auxiliary_scale,
        6,
    )
    prior_score = round(
        raw_prior_score * auxiliary_scale,
        6,
    )

    if metadata_score > 0:
        signals.append(
            AttributionSignal(
                name="metadata_overlap",
                contribution=metadata_score,
                detail=_match_detail(
                    "metadata",
                    metadata_matches,
                ),
            )
        )

    if prior_score > 0:
        signals.append(
            AttributionSignal(
                name="evidence_type_prior",
                contribution=prior_score,
                detail=(
                    f"{evidence.evidence_type} evidence "
                    f"weakly supports the "
                    f"{stage.stage_id} stage."
                ),
            )
        )

    low_value_matches = (
        title_tokens | description_tokens
    ) & LOW_VALUE_TERMS
    low_value_penalty = 0.0

    if low_value_matches:
        low_value_penalty = min(
            0.30,
            0.12 + 0.04 * (
                len(low_value_matches) - 1
            ),
        )
        signals.append(
            AttributionSignal(
                name="low_value_activity_penalty",
                contribution=-low_value_penalty,
                detail=(
                    "Low-value activity terms detected: "
                    + ", ".join(
                        sorted(low_value_matches)
                    )
                    + "."
                ),
            )
        )

    raw_score = (
        title_score
        + description_score
        + metadata_score
        + prior_score
        - low_value_penalty
    )
    score = round(
        min(1.0, max(0.0, raw_score)),
        6,
    )

    content_matched_terms = sorted(
        title_matches
        | description_matches
    )[:MAX_MATCHED_TERMS_REPORTED]

    matched_terms = sorted(
        title_matches
        | description_matches
        | metadata_matches
    )[:MAX_MATCHED_TERMS_REPORTED]

    return DeterministicAttributionCandidate(
        roadmap_node_id=stage.stage_id,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash=roadmap.roadmap_hash,
            roadmap_stage_hash=stage.content_hash,
            roadmap_node_id=stage.stage_id,
            snapshot_version=(
                roadmap.snapshot_version
            ),
            canonicalization_version=(
                roadmap.canonicalization_version
            ),
        ),
        score=score,
        content_score=round(
            min(
                1.0,
                max(0.0, lexical_score),
            ),
            6,
        ),
        matched_terms=matched_terms,
        content_matched_terms=(
            content_matched_terms
        ),
        signals=signals,
    )


def _has_cross_stage_ambiguity(
    candidates: List[
        DeterministicAttributionCandidate
    ],
) -> bool:
    if len(candidates) < 2:
        return False

    top = candidates[0]

    if top.score < MINIMUM_CANDIDATE_SCORE:
        return False

    top_terms = set(
        top.content_matched_terms
    )

    for alternative in candidates[1:]:
        if (
            alternative.score
            < CROSS_STAGE_MINIMUM_SCORE
        ):
            continue

        alternative_terms = set(
            alternative.content_matched_terms
        )
        top_distinct_terms = (
            top_terms - alternative_terms
        )
        alternative_distinct_terms = (
            alternative_terms - top_terms
        )

        if (
            len(top_distinct_terms)
            >= CROSS_STAGE_MINIMUM_DISTINCT_TERMS
            and len(alternative_distinct_terms)
            >= CROSS_STAGE_MINIMUM_DISTINCT_TERMS
        ):
            return True

    return False


def _is_explicit_revert(title: str) -> bool:
    normalized_tokens = TOKEN_PATTERN.findall(
        unicodedata.normalize(
            "NFKC",
            title,
        ).casefold()
    )

    if not normalized_tokens:
        return False

    return (
        normalized_tokens[0]
        in EXPLICIT_REVERT_TITLE_TERMS
    )


def _decide(
    *,
    selected: List[
        DeterministicAttributionCandidate
    ],
    score_margin: float,
) -> tuple[str, str]:
    if not selected:
        return (
            "abstain",
            "The roadmap contains no candidate stages.",
        )

    top = selected[0]

    if top.score < MINIMUM_CANDIDATE_SCORE:
        return (
            "abstain",
            "No roadmap stage reached the minimum "
            "candidate score.",
        )

    if (
        len(top.matched_terms)
        < MINIMUM_MATCHED_TERMS
    ):
        return (
            "abstain",
            "The strongest candidate had insufficient "
            "lexical support.",
        )

    if len(selected) > 1:
        content_score_margin = round(
            max(
                0.0,
                selected[0].content_score
                - selected[1].content_score,
            ),
            6,
        )

        if (
            score_margin < MINIMUM_TOP_MARGIN
            and content_score_margin
            < MINIMUM_TOP_MARGIN
        ):
            return (
                "abstain",
                "The top roadmap candidates were too close "
                "to distinguish safely.",
            )

    return "suggest", ""


def _bounded_overlap(
    *,
    matched: Set[str],
    source: Set[str],
    weight: float,
    cap_terms: int,
) -> float:
    if not matched or not source:
        return 0.0

    capped_match_count = min(
        len(matched),
        cap_terms,
    )
    capped_source_size = min(
        max(len(source), 1),
        cap_terms,
    )

    coverage = (
        capped_match_count
        / capped_source_size
    )
    saturation = (
        math.log1p(capped_match_count)
        / math.log1p(cap_terms)
    )

    return round(
        weight * (
            0.65 * coverage
            + 0.35 * saturation
        ),
        6,
    )


def _stage_tokens(
    content: Dict[str, Any],
) -> Set[str]:
    fields = [
        content.get("title"),
        content.get("purpose"),
        content.get("tasks"),
        content.get("objective"),
        content.get("why_it_matters"),
        content.get("commands"),
        content.get("expected_outputs"),
        content.get("acceptance_criteria"),
        content.get("validation_checks"),
        content.get("portfolio_artifact"),
        content.get("unlock_condition"),
        content.get("guided_steps"),
    ]

    return _tokenize_values(fields)


def _metadata_tokens(
    metadata: Dict[str, Any],
) -> Set[str]:
    allowed_keys = {
        "base_branch",
        "branch",
        "conclusion",
        "event",
        "head_branch",
        "labels",
        "state",
        "tag_name",
        "target_commitish",
    }

    values = [
        metadata.get(key)
        for key in sorted(allowed_keys)
        if key in metadata
    ]

    return _tokenize_values(values)


def _tokenize_values(
    values: Iterable[Any],
) -> Set[str]:
    tokens: Set[str] = set()

    for value in values:
        for text in _iter_text(value):
            tokens.update(_tokenize(text))

    return tokens


def _iter_text(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
        return

    if isinstance(value, dict):
        for key in sorted(value):
            yield from _iter_text(value[key])
        return

    if isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_text(item)


def _tokenize(value: str) -> Set[str]:
    normalized = unicodedata.normalize(
        "NFKC",
        value,
    ).casefold()

    cleaned = "".join(
        character
        for character in normalized
        if (
            unicodedata.category(character)
            not in {"Cc", "Cf"}
            or character in {"\n", "\t"}
        )
    )

    return {
        token
        for token in TOKEN_PATTERN.findall(cleaned)
        if (
            len(token) >= 2
            and token not in STOP_WORDS
        )
    }


def _match_detail(
    source_name: str,
    matches: Set[str],
) -> str:
    return (
        f"Matched {source_name} terms: "
        + ", ".join(sorted(matches))
        + "."
    )
