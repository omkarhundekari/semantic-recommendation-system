from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence


class ClauseRole(str, Enum):
    GOAL = "goal"
    SKILL_HELD = "skill_held"
    SKILL_TARGET = "skill_target"
    ROLE = "role"
    STACK_PREFERENCE = "stack_preference"
    CONSTRAINT = "constraint"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ConceptCandidate:
    surface_form: str
    normalized_form: str
    clause_role: ClauseRole
    char_span: tuple[int, int]


@dataclass(frozen=True)
class StructuralQueryUnderstanding:
    raw_query: str
    candidates: Sequence[ConceptCandidate]
    role_hint: Optional[str]
    timeline_hint: Optional[str]


# This is grammatical vocabulary, not a technology taxonomy.
FUNCTION_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "been",
    "but",
    "can",
    "could",
    "do",
    "for",
    "from",
    "have",
    "help",
    "i",
    "i'm",
    "im",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "please",
    "something",
    "that",
    "the",
    "this",
    "to",
    "using",
    "want",
    "with",
    "you",
}


# Generic project framing words are also not technical concepts.
PROJECT_FRAMING_WORDS = {
    "app",
    "application",
    "build",
    "building",
    "create",
    "develop",
    "idea",
    "make",
    "portfolio",
    "project",
    "role",
    "system",
    "tool",
}


# Generic modifiers should not become standalone concepts.
GENERIC_MODIFIERS = {
    # Degree / familiarity / generic description.
    "basic",
    "before",
    "comfortable",
    "familiar",
    "impressive",
    "realistic",
    "simple",
    "small",
    "some",
    "useful",

    # Intent / experience verbs. These may still act as
    # structural boundaries in the raw query, but they are not
    # technical concepts themselves.
    "know",
    "used",
    "worked",
    "experience",
    "learn",
    "practice",
    "improve",
    "teach",
    "teaches",
    "targeting",
    "become",
    "need",

    # Conversational / discourse filler.
    "already",
    "basically",
    "bro",
    "give",
    "good",
    "hey",
    "idk",
    "just",
    "like",
    "maybe",
    "now",
    "not",
    "pls",
    "really",
    "sure",
    "u",
    "stuff",
    "tho",
    "type",
    "umm",
    "what",
    "where",
    "would",
    "look",
    "looks",

    # Generic outcome / framing nouns that should not be resolved
    # as technical concepts in isolation.
    "job",
    "resume",
    "skills",

    "by",
}


ROLE_PATTERNS = [
    re.compile(
        r"\bfor\s+(?:an?\s+|the\s+)?"
        r"([a-z0-9+#.-]+(?:\s+[a-z0-9+#.-]+){0,3})"
        r"\s+role\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b("
        r"[a-z0-9+#.-]+(?:\s+[a-z0-9+#.-]+){0,2}"
        r"\s+engineer"
        r")\b"
        r"(?=\s+(?:portfolio|project|role)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b("
        r"[a-z0-9+#.-]+(?:\s+[a-z0-9+#.-]+){0,2}"
        r"\s+analyst"
        r")\b"
        r"(?=\s+(?:portfolio|project|role)\b)",
        re.IGNORECASE,
    ),
]


TIMELINE_PATTERN = re.compile(
    r"\b("
    r"\d+\s*(?:day|days|week|weeks|month|months)"
    r"|(?:one|two|three|four)\s+"
    r"(?:day|days|week|weeks|month|months)"
    r"|this weekend"
    r"|weekend"
    r")\b",
    re.IGNORECASE,
)


SKILL_HELD_PATTERNS = [
    re.compile(
        r"\b(?:i\s+)?"
        r"(?:know|have\s+used|used|am\s+familiar\s+with|"
        r"i'm\s+familiar\s+with|im\s+familiar\s+with|"
        r"am\s+comfortable\s+with|i'm\s+comfortable\s+with|"
        r"comfortable\s+with)"
        r"\s+(.+?)"
        r"(?="
        r",\s*(?:but|and\s+want|have)"
        r"|\s+but\b"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),

    # Explicit prior-experience constructions.
    #
    # These must outrank the generic "with X" stack pattern:
    #
    #   I've worked with Python before.
    #   I have experience with React.
    #   I have worked with FastAPI.
    re.compile(
        r"\b(?:"
        r"i(?:'ve|\s+have)?\s+worked\s+with"
        r"|i\s+have\s+experience\s+with"
        r"|have\s+experience\s+with"
        r")"
        r"\s+(.+?)"
        r"(?="
        r",\s*(?:but|and)"
        r"|\s+but\b"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),
]


SKILL_TARGET_PATTERNS = [
    re.compile(
        r"\b(?:i\s+)?want\s+to\s+learn\s+(.+?)"
        r"(?=\s+by\b|[,;.!?]|$)",
        re.IGNORECASE,
    ),
]


STACK_PREFERENCE_PATTERNS = [
    re.compile(
        r"\busing\s+(.+?)"
        r"(?="
        r"\s+(?:for|in|but|that|which|who|while|so)\b"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bwith\s+(.+?)"
        r"(?="
        r"\s+(?:for|in|but|that|which|who|while|so)\b"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),
]


GOAL_PATTERNS = [
    re.compile(
        r"\b(?:i\s+want\s+to\s+|want\s+to\s+)?"
        r"(?:build|create|make|develop)\s+(.+?)"
        r"(?="
        r"\s+(?:for|using|with)\b"
        r"|,\s*(?:but|and)"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),

    # Generic desire construction:
    #
    #   I want a machine learning project.
    #   I want a React frontend portfolio project.
    #
    # This is grammatical structure only. It does not contain
    # technology names or domain vocabulary.
    re.compile(
        r"\b(?:i\s+)?want\s+(?!to\b)"
        r"(?:an?\s+)?"
        r"(.+?)"
        r"\s+(?:portfolio\s+)?"
        r"(?:project|app|application|tool|system|product)"
        r"(?="
        r"\s+(?:for|using|with)\b"
        r"|,\s*(?:but|and)"
        r"|[;.!?]"
        r"|$"
        r")",
        re.IGNORECASE,
    ),
]


TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9'])"
    r"[A-Za-z][A-Za-z0-9+#-]*"
    r"(?:\.[A-Za-z0-9+#-]+)*"
    r"(?![A-Za-z0-9'])"
)


def _clean(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        value.strip(" \t\r\n,;:.!?"),
    )


def _normalize(value: str) -> str:
    return _clean(value).lower()


def _is_noise_token(value: str) -> bool:
    normalized = _normalize(value)

    return (
        not normalized
        or normalized in FUNCTION_WORDS
        or normalized in PROJECT_FRAMING_WORDS
        or normalized in GENERIC_MODIFIERS
    )


def _collect_pattern_spans(
    query: str,
) -> List[tuple[int, int, ClauseRole]]:
    spans: List[tuple[int, int, ClauseRole]] = []

    groups = [
        (ROLE_PATTERNS, ClauseRole.ROLE),
        (SKILL_HELD_PATTERNS, ClauseRole.SKILL_HELD),
        (SKILL_TARGET_PATTERNS, ClauseRole.SKILL_TARGET),
        (
            STACK_PREFERENCE_PATTERNS,
            ClauseRole.STACK_PREFERENCE,
        ),
        (GOAL_PATTERNS, ClauseRole.GOAL),
    ]

    for patterns, role in groups:
        for pattern in patterns:
            for match in pattern.finditer(query):
                start, end = match.span(1)
                spans.append((start, end, role))

    for match in TIMELINE_PATTERN.finditer(query):
        spans.append(
            (
                match.start(),
                match.end(),
                ClauseRole.CONSTRAINT,
            )
        )

    return spans


def _role_for_span(
    start: int,
    end: int,
    spans: Sequence[tuple[int, int, ClauseRole]],
) -> ClauseRole:
    matching = [
        role
        for span_start, span_end, role in spans
        if start >= span_start and end <= span_end
    ]

    if not matching:
        return ClauseRole.UNKNOWN

    # More specific structural roles beat broad goal spans.
    priority = (
        ClauseRole.CONSTRAINT,
        ClauseRole.ROLE,
        ClauseRole.SKILL_HELD,
        ClauseRole.SKILL_TARGET,
        ClauseRole.STACK_PREFERENCE,
        ClauseRole.GOAL,
    )

    for role in priority:
        if role in matching:
            return role

    return matching[0]


def _extract_role_hint(query: str) -> Optional[str]:
    for pattern in ROLE_PATTERNS:
        match = pattern.search(query)

        if match:
            return _clean(match.group(1))

    return None


def _extract_timeline_hint(
    query: str,
) -> Optional[str]:
    match = TIMELINE_PATTERN.search(query)

    if not match:
        return None

    return _clean(match.group(1))


def _token_candidates(
    query: str,
    spans: Sequence[tuple[int, int, ClauseRole]],
) -> List[ConceptCandidate]:
    candidates: List[ConceptCandidate] = []

    for match in TOKEN_PATTERN.finditer(query):
        surface = _clean(match.group(0))

        if _is_noise_token(surface):
            continue

        role = _role_for_span(
            match.start(),
            match.end(),
            spans,
        )

        # Timeline words belong to the constraint channel, not
        # the technical-concept channel.
        if role == ClauseRole.CONSTRAINT:
            continue

        candidates.append(
            ConceptCandidate(
                surface_form=surface,
                normalized_form=_normalize(surface),
                clause_role=role,
                char_span=(
                    match.start(),
                    match.end(),
                ),
            )
        )

    return candidates


def _phrase_candidates(
    query: str,
    spans: Sequence[tuple[int, int, ClauseRole]],
) -> List[ConceptCandidate]:
    candidates: List[ConceptCandidate] = []

    for start, end, role in spans:
        if role not in {
            ClauseRole.ROLE,
            ClauseRole.GOAL,
        }:
            continue

        text = query[start:end]

        useful_tokens = [
            _clean(match.group(0))
            for match in TOKEN_PATTERN.finditer(text)
            if not _is_noise_token(match.group(0))
        ]

        if len(useful_tokens) < 2:
            continue

        if len(useful_tokens) > 3:
            continue

        phrase = " ".join(useful_tokens)

        candidates.append(
            ConceptCandidate(
                surface_form=phrase,
                normalized_form=_normalize(phrase),
                clause_role=role,
                char_span=(start, end),
            )
        )

    return candidates


def _dedupe_candidates(
    candidates: Sequence[ConceptCandidate],
) -> List[ConceptCandidate]:
    result: List[ConceptCandidate] = []
    seen = set()

    for candidate in candidates:
        # Candidate identity is occurrence-aware.
        #
        # The same normalized concept with the same clause role
        # may legitimately appear more than once in the user's
        # query. Character position distinguishes those
        # occurrences and must survive into later span generation.
        key = (
            candidate.normalized_form,
            candidate.clause_role,
            candidate.char_span,
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(candidate)

    return result


def extract_concept_candidates(
    query: str,
) -> List[ConceptCandidate]:
    spans = _collect_pattern_spans(query)

    candidates = (
        _phrase_candidates(query, spans)
        + _token_candidates(query, spans)
    )

    return _dedupe_candidates(candidates)


def understand_query_structure(
    query: str,
) -> StructuralQueryUnderstanding:
    return StructuralQueryUnderstanding(
        raw_query=query,
        candidates=extract_concept_candidates(query),
        role_hint=_extract_role_hint(query),
        timeline_hint=_extract_timeline_hint(query),
    )
