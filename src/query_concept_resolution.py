from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence

from domain_taxonomy import (
    get_domain_family,
    get_focus_from_category,
    normalize_value,
)
from github_corpus_search import (
    search_github_project_corpus,
)
from project_corpus_search import (
    search_project_corpus,
)
from query_concept_understanding import (
    ClauseRole,
    ConceptCandidate,
    understand_query_structure,
)
from research_retrieval_service import (
    retrieve_ranked_evidence,
)


class ResolutionStatus(str, Enum):
    EVIDENCE_RESOLVED = "evidence_resolved"
    SUPPORTED_AMBIGUOUS = "supported_ambiguous"
    SUPPORTED_WEAK = "supported_weak"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class ConceptEvidenceHit:
    source_type: str
    title: str
    category: Optional[str]
    focus: str
    family: str
    score: float

    # Keep lexical provenance separate from semantic/domain score.
    lexical_match: bool
    lexical_coverage: float
    bm25_score: Optional[float]


@dataclass(frozen=True)
class GeneratedConceptSpan:
    surface_form: str
    normalized_form: str

    # Exact interval in the original user query covering the
    # generated reading.
    char_span: tuple[int, int]

    # Exact occurrence-level provenance for the atomic candidates
    # from which this span was composed.
    constituent_char_spans: tuple[
        tuple[int, int],
        ...
    ]

    # Candidate-segment identity is preserved now so later
    # containment logic never has to reconstruct structural
    # boundaries from strings.
    segment_index: int


@dataclass(frozen=True)
class ResolvedConceptSpan:
    surface_form: str
    normalized_form: str
    clause_role: ClauseRole
    ngram_size: int

    resolution_status: ResolutionStatus

    confidence: float

    inferred_focus: Optional[str]
    inferred_family: Optional[str]

    domain_margin: float

    support_count: int
    source_type_count: int

    lexical_support_count: int
    lexical_source_type_count: int
    lexical_coverage: float
    top_bm25_score: Optional[float]

    supporting_evidence: Sequence[ConceptEvidenceHit]

    # L2.7a structural provenance.
    #
    # These fields do not participate in resolution, confidence,
    # status assignment, domain inference, or sorting.
    char_span: Optional[tuple[int, int]] = None
    constituent_char_spans: tuple[
        tuple[int, int],
        ...
    ] = tuple()
    segment_index: Optional[int] = None


GENERIC_SPAN_NOISE = {
    "project",
    "portfolio",
    "app",
    "application",
    "tool",
    "system",
    "something",
    "build",
    "building",
    "create",
    "make",
    "develop",
    "using",
    "with",
    "for",
    "role",
}


# These words indicate a semantic/intention transition in the
# user's original wording.
#
# They are deliberately separate from GENERIC_SPAN_NOISE.
# A transition word is not necessarily meaningless text; it
# simply must prevent unrelated concept candidates on opposite
# sides from being manufactured into one n-gram.
#
# This is especially important for terse or ungrammatical input:
#
#   rag basics know want rag evaluator
#   python used before now want python backend
#   qwen milvus gradio want retrieval project
#
# Correct punctuation or fully grammatical English is not
# required for these transitions to remain structurally useful.
INTENT_TRANSITION_BOUNDARIES = {
    "want",
    "need",
    "know",
    "used",
    "learn",
    "practice",
    "improve",
    "teach",
    "teaches",
    "targeting",
    "become",
}


# These terminate candidate n-grams.
#
# They are grammatical boundaries, not technology vocabulary.
HARD_BOUNDARY_PATTERN = re.compile(
    r"""
    [,;.!?:]
    |
    \bbut\b
    |
    \bhowever\b
    |
    \balthough\b
    |
    \bthough\b
    |
    \bwhereas\b
    |
    \busing\b
    |
    \bwith\b
    |
    \bfor\b
    |
    \bby\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"[A-Za-z][A-Za-z0-9+#-]*"
    r"(?:\.[A-Za-z0-9+#-]+)*"
    r"(?![A-Za-z0-9])"
)


def _normalize_span(value: str) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9+#.-]+",
            str(value or "").lower(),
        )
    )


def _surface_tokens(value: str) -> List[str]:
    return [
        token
        for token in _normalize_span(value).split()
        if token
    ]


def _score_from_item(item: Dict) -> float:
    # BM25 is intentionally NOT used here.
    #
    # This score is for semantic/domain ranking only.
    for key in (
        "rerank_score",
        "semantic_score",
        "rrf_score",
        "score",
    ):
        value = item.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return 0.0


def _bm25_from_item(
    item: Dict,
) -> Optional[float]:
    value = item.get("bm25_score")

    if isinstance(value, (int, float)):
        return float(value)

    return None


def _resolve_focus(item: Dict) -> str:
    category = item.get("category")

    focus = get_focus_from_category(category)

    if focus != "general":
        return focus

    normalized_category = normalize_value(category)

    if get_domain_family(normalized_category) != "general":
        return normalized_category

    return "general"


def _item_text(
    item: Dict,
) -> str:
    fields = (
        "title",
        "name",
        "abstract",
        "content",
        "tags",
        "skills",
        "technology_signals",
        "architecture_signals",
        "readme_excerpt",
        "selection_reason",
    )

    return " ".join(
        str(item.get(field, "") or "")
        for field in fields
    )


def _token_occurs(
    token: str,
    text: str,
) -> bool:
    token = token.strip().lower()

    if not token:
        return False

    normalized_text = text.lower()

    return bool(
        re.search(
            rf"(?<![a-z0-9])"
            rf"{re.escape(token)}"
            rf"(?![a-z0-9])",
            normalized_text,
        )
    )


def _lexical_coverage(
    surface_form: str,
    item: Dict,
) -> float:
    tokens = _surface_tokens(surface_form)

    if not tokens:
        return 0.0

    text = _item_text(item)

    matched = sum(
        1
        for token in tokens
        if _token_occurs(token, text)
    )

    return matched / len(tokens)


def _tokens_match_with_proximity(
    query_tokens: Sequence[str],
    text_tokens: Sequence[str],
    *,
    max_gap: int = 4,
) -> bool:
    """
    Require query tokens to occur in order and locally.

    This prevents a composite span such as:

        python react ai

    from being declared lexically supported merely because
    all three words occur somewhere in a long document.
    """
    if not query_tokens:
        return False

    first = query_tokens[0]

    for start, token in enumerate(text_tokens):
        if token != first:
            continue

        position = start
        matched = True

        for expected in query_tokens[1:]:
            search_end = min(
                len(text_tokens),
                position + max_gap + 2,
            )

            next_position = None

            for candidate_position in range(
                position + 1,
                search_end,
            ):
                if (
                    text_tokens[candidate_position]
                    == expected
                ):
                    next_position = candidate_position
                    break

            if next_position is None:
                matched = False
                break

            position = next_position

        if matched:
            return True

    return False


def _lexical_match(
    surface_form: str,
    item: Dict,
) -> bool:
    """
    Single-token concepts require literal token occurrence.

    Multi-token concepts require ordered local occurrence.
    Document-wide token co-occurrence is not sufficient.
    """
    tokens = _surface_tokens(surface_form)

    if not tokens:
        return False

    raw_text = _item_text(item)

    if len(tokens) == 1:
        return _token_occurs(
            tokens[0],
            raw_text,
        )

    text_tokens = _surface_tokens(
        raw_text
    )

    return _tokens_match_with_proximity(
        tokens,
        text_tokens,
        max_gap=4,
    )


def _evidence_hit(
    item: Dict,
    *,
    surface_form: str,
    source_type: str,
) -> ConceptEvidenceHit:
    focus = _resolve_focus(item)
    family = get_domain_family(focus)

    coverage = _lexical_coverage(
        surface_form,
        item,
    )

    return ConceptEvidenceHit(
        source_type=source_type,
        title=str(
            item.get("title", "")
            or item.get("name", "")
            or ""
        ),
        category=(
            str(item.get("category"))
            if item.get("category") is not None
            else None
        ),
        focus=focus,
        family=family,
        score=_score_from_item(item),
        lexical_match=_lexical_match(
            surface_form,
            item,
        ),
        lexical_coverage=round(
            coverage,
            4,
        ),
        bm25_score=_bm25_from_item(
            item,
        ),
    )


def _collect_span_evidence(
    span: str,
    *,
    top_k: int = 6,
) -> List[ConceptEvidenceHit]:
    research = retrieve_ranked_evidence(
        query=span,
        top_k=top_k,
        strategy="hybrid_rrf",
    )

    projects = search_project_corpus(
        span,
        top_k=top_k,
        domain_filter=None,
    )

    github = search_github_project_corpus(
        span,
        top_k=top_k,
        domain_filter=None,
    )

    hits = [
        *[
            _evidence_hit(
                item,
                surface_form=span,
                source_type="research_paper",
            )
            for item in research
        ],
        *[
            _evidence_hit(
                item,
                surface_form=span,
                source_type="project_pattern",
            )
            for item in projects
        ],
        *[
            _evidence_hit(
                item,
                surface_form=span,
                source_type="github_repository",
            )
            for item in github
        ],
    ]

    # Evidence existence and taxonomy classification are
    # separate concerns.
    #
    # A lexically matching hit must survive collection even when
    # its category is not yet represented by the curated taxonomy.
    #
    # Domain inference will filter unclassified/general hits later.
    return hits


def _lexically_supported_hits(
    hits: Sequence[ConceptEvidenceHit],
) -> List[ConceptEvidenceHit]:
    return [
        hit
        for hit in hits
        if hit.lexical_match
    ]


def _domain_scores(
    hits: Sequence[ConceptEvidenceHit],
) -> Dict[str, float]:
    by_family: Dict[str, Dict[str, float]] = {}

    for hit in hits:
        family_bucket = by_family.setdefault(
            hit.family,
            {},
        )

        previous = family_bucket.get(
            hit.source_type,
            0.0,
        )

        family_bucket[hit.source_type] = max(
            previous,
            max(hit.score, 0.0001),
        )

    return {
        family: sum(source_scores.values())
        for family, source_scores in by_family.items()
    }


def _focus_scores(
    hits: Sequence[ConceptEvidenceHit],
) -> Dict[str, float]:
    scores: Dict[str, float] = {}

    for hit in hits:
        scores[hit.focus] = (
            scores.get(hit.focus, 0.0)
            + max(hit.score, 0.0001)
        )

    return scores


def _best_and_margin(
    scores: Dict[str, float],
) -> tuple[Optional[str], float]:
    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if not ranked:
        return None, 0.0

    best_name, best_score = ranked[0]

    # Margin measures separation between competing hypotheses.
    #
    # With only one observed family/focus there is no runner-up,
    # so separation is not measurable. Returning 1.0 here would
    # incorrectly convert absence of competition into maximal
    # agreement.
    if len(ranked) == 1:
        return best_name, 0.0

    second_score = ranked[1][1]

    margin = (
        (best_score - second_score)
        / best_score
        if best_score > 0
        else 0.0
    )

    return best_name, round(
        margin,
        4,
    )


def _confidence(
    *,
    hits: Sequence[ConceptEvidenceHit],
    margin: float,
) -> float:
    if not hits:
        return 0.0

    source_types = {
        hit.source_type
        for hit in hits
    }

    source_diversity = min(
        len(source_types) / 3.0,
        1.0,
    )

    support_strength = min(
        len(hits) / 6.0,
        1.0,
    )

    confidence = (
        0.45 * source_diversity
        + 0.30 * support_strength
        + 0.25 * margin
    )

    return round(
        min(max(confidence, 0.0), 1.0),
        4,
    )


def _candidate_tokens(
    query: str,
) -> List[ConceptCandidate]:
    structure = understand_query_structure(
        query
    )

    candidates = sorted(
        structure.candidates,
        key=lambda candidate: (
            candidate.char_span[0],
            candidate.char_span[1],
        ),
    )

    # Phrase candidates and token candidates can overlap.
    # For n-gram generation, retain atomic candidates only.
    atomic = [
        candidate
        for candidate in candidates
        if len(
            candidate.normalized_form.split()
        ) == 1
    ]

    return atomic


def _has_hard_boundary(
    query: str,
    left: ConceptCandidate,
    right: ConceptCandidate,
) -> bool:
    between = query[
        left.char_span[1]
        :
        right.char_span[0]
    ]

    if HARD_BOUNDARY_PATTERN.search(
        between
    ):
        return True

    # Some framing/noise words may already have been removed
    # by structural candidate extraction.
    #
    # They still occupy real positions in the user's original
    # query and therefore must prevent artificial adjacency.
    #
    # Example:
    #
    #   React project and TypeScript
    #
    # Candidate extraction may expose only React + TypeScript.
    # The original "project" token must still stop us from
    # manufacturing the span "React TypeScript".
    between_tokens = {
        _normalize_span(match.group(0))
        for match in TOKEN_PATTERN.finditer(
            between
        )
    }

    return bool(
        (
            between_tokens
            & GENERIC_SPAN_NOISE
        )
        or (
            between_tokens
            & INTENT_TRANSITION_BOUNDARIES
        )
    )


def _candidate_segments(
    query: str,
) -> List[List[ConceptCandidate]]:
    candidates = _candidate_tokens(query)

    if not candidates:
        return []

    segments: List[List[ConceptCandidate]] = []
    current: List[ConceptCandidate] = []
    previous_valid: Optional[ConceptCandidate] = None

    for candidate in candidates:
        # A removed/noise token is a boundary, not whitespace.
        #
        # Otherwise:
        #
        #   React project and TypeScript
        #
        # would become the artificial span:
        #
        #   React TypeScript
        if not _valid_candidate(candidate):
            if current:
                segments.append(current)
                current = []

            previous_valid = None
            continue

        if (
            previous_valid is not None
            and _has_hard_boundary(
                query,
                previous_valid,
                candidate,
            )
        ):
            if current:
                segments.append(current)

            current = []

        current.append(candidate)
        previous_valid = candidate

    if current:
        segments.append(current)

    return segments


def _valid_candidate(
    candidate: ConceptCandidate,
) -> bool:
    normalized = candidate.normalized_form

    return bool(
        normalized
        and normalized
        not in GENERIC_SPAN_NOISE
    )


def generate_structured_ngram_spans(
    query: str,
    *,
    max_n: int = 4,
) -> List[GeneratedConceptSpan]:
    """
    Generate structurally valid concept spans while preserving
    occurrence-level provenance from the original query.

    L2.7a intentionally preserves the existing generation
    semantics. This function adds metadata only.
    """
    spans: List[GeneratedConceptSpan] = []

    # Structured generation is occurrence-aware.
    #
    # The same normalized concept may legitimately occur more
    # than once in the user's query. Those occurrences must remain
    # distinct because later containment/selection depends on
    # original-query position.
    #
    # We still collapse duplicate structural readings of the same
    # occurrence, such as an extracted phrase and an atomic
    # composition that resolve to the same normalized text over
    # the same interval.
    seen_occurrences = set()

    for segment_index, segment in enumerate(
        _candidate_segments(query)
    ):
        for size in range(
            1,
            max_n + 1,
        ):
            for start in range(
                0,
                len(segment) - size + 1,
            ):
                group = segment[
                    start : start + size
                ]

                # Preserve the existing structural rule exactly:
                # do not manufacture phrases across role changes.
                roles = {
                    candidate.clause_role
                    for candidate in group
                    if candidate.clause_role
                    != ClauseRole.UNKNOWN
                }

                if (
                    len(group) > 1
                    and len(roles) > 1
                ):
                    continue

                surface = " ".join(
                    candidate.surface_form
                    for candidate in group
                )

                normalized = _normalize_span(
                    surface
                )

                if not normalized:
                    continue

                char_span = (
                    group[0].char_span[0],
                    group[-1].char_span[1],
                )

                # Occurrence identity is position-aware.
                #
                # Two equal concepts at different locations remain
                # distinct. Multiple generation paths that describe
                # the same normalized reading over the exact same
                # interval are deliberately collapsed.
                occurrence_key = (
                    normalized,
                    char_span,
                )

                if occurrence_key in seen_occurrences:
                    continue

                seen_occurrences.add(
                    occurrence_key
                )

                spans.append(
                    GeneratedConceptSpan(
                        surface_form=surface,
                        normalized_form=normalized,
                        char_span=char_span,
                        constituent_char_spans=tuple(
                            candidate.char_span
                            for candidate in group
                        ),
                        segment_index=segment_index,
                    )
                )

    return spans


def generate_ngram_spans(
    query: str,
    *,
    max_n: int = 4,
) -> List[str]:
    """
    Backwards-compatible string-only view of generated spans.

    L2.7a keeps this public interface unchanged.
    """
    # This legacy API cannot represent occurrence identity.
    #
    # Preserve its historical behavior exactly:
    # globally deduplicate by normalized form while retaining
    # first-occurrence / generation order.
    result: List[str] = []
    seen = set()

    for span in generate_structured_ngram_spans(
        query,
        max_n=max_n,
    ):
        if span.normalized_form in seen:
            continue

        seen.add(
            span.normalized_form
        )
        result.append(
            span.surface_form
        )

    return result



# =========================================================
# L2.7a.6g — STRUCTURAL ROLE OVERRIDES
#
# Role assignment now has three deliberately separate sources:
#
#   1. bounded role constructions
#   2. cue-scope propagation
#   3. weak role morphology/context fallback
#
# A bounded construction is allowed to override cue scope
# because both edges of the construction are explicit.
#
# Weak morphology is intentionally much weaker: it may only
# supply ROLE when cue scope returned UNKNOWN.
#
# None of these rules inspect technology identity or corpus
# evidence.
# =========================================================


_SHADOW_BOUNDED_ROLE_PATTERNS = (
    # Example:
    #
    #   I want something for a data engineer role.
    #
    # "for" opens the construction and role/roles closes it.
    # This is structurally different from the old greedy clause
    # captures because both boundaries are explicit.
    re.compile(
        r"\bfor\s+"
        r"(?:an?\s+|the\s+)?"
        r"("
        r"[A-Za-z][A-Za-z0-9+#.-]*"
        r"(?:\s+[A-Za-z][A-Za-z0-9+#.-]*){0,4}"
        r")"
        r"\s+roles?\b",
        re.IGNORECASE,
    ),
)


# Occupational heads are a deliberately small closed-class
# grammatical/morphological signal, not an open-world dictionary
# of job titles.
_SHADOW_ROLE_HEAD_PATTERN = re.compile(
    r"\b(?:"
    r"engineer"
    r"|analyst"
    r"|scientist"
    r"|developer"
    r"|architect"
    r"|administrator"
    r")s?\b",
    re.IGNORECASE,
)


# Weak role morphology requires explicit career/portfolio
# framing nearby. The occupational head alone is not enough.
_SHADOW_ROLE_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"portfolio"
    r"|career"
    r"|job"
    r"|jobs"
    r"|role"
    r"|roles"
    r")\b",
    re.IGNORECASE,
)


def _shadow_bounded_role_spans(
    query: str,
):
    """
    Return closed ROLE construction intervals.

    Output tuples:

        (
            captured_start,
            captured_end,
            full_start,
            full_end,
        )

    Candidate identity is irrelevant; only source positions are
    used.
    """
    result = []

    for pattern in (
        _SHADOW_BOUNDED_ROLE_PATTERNS
    ):
        for match in pattern.finditer(
            query
        ):
            captured_start, captured_end = (
                match.span(1)
            )

            result.append(
                (
                    captured_start,
                    captured_end,
                    match.start(),
                    match.end(),
                )
            )

    return result


def _shadow_bounded_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
) -> ClauseRole:
    """
    Strong ROLE override for candidates contained inside a
    closed role construction.
    """
    if char_span is None:
        return ClauseRole.UNKNOWN

    start, end = char_span

    for (
        role_start,
        role_end,
        _full_start,
        _full_end,
    ) in _shadow_bounded_role_spans(
        query
    ):
        if (
            start >= role_start
            and end <= role_end
        ):
            return ClauseRole.ROLE

    return ClauseRole.UNKNOWN


def _shadow_role_morphology_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    segment_index: Optional[int] = None,
) -> ClauseRole:
    """
    Weak ROLE fallback.

    This helper is intentionally conservative:

      * the candidate's own segment must contain an
        occupational head; and
      * the nearby segment/framing context must contain a
        career/portfolio marker.

    It must never override a non-UNKNOWN cue-scope result.
    """
    if char_span is None:
        return ClauseRole.UNKNOWN

    start, end = char_span

    matching_bounds = None

    for (
        current_segment_index,
        left_scope_start,
        segment_start,
        segment_end,
        _segment,
    ) in _shadow_segment_scope_bounds(
        query
    ):
        if (
            start >= segment_start
            and end <= segment_end
        ):
            if (
                segment_index is not None
                and current_segment_index
                != segment_index
            ):
                continue

            matching_bounds = (
                left_scope_start,
                segment_start,
                segment_end,
            )
            break

    if matching_bounds is None:
        return ClauseRole.UNKNOWN

    (
        left_scope_start,
        segment_start,
        segment_end,
    ) = matching_bounds

    segment_text = query[
        segment_start:segment_end
    ]

    # Candidate hygiene may deliberately remove framing
    # vocabulary such as:
    #
    #   portfolio
    #   role
    #   roles
    #   job
    #
    # Those tokens must stay out of technical candidate
    # generation, but weak role morphology still needs to inspect
    # them as raw structural context.
    #
    # Therefore the morphology context extends from this
    # segment's left scope through the raw text immediately after
    # the candidate segment, stopping at the next candidate
    # segment when one exists.
    next_segment_start = len(query)

    for (
        next_segment_index,
        _next_left_scope_start,
        next_start,
        _next_end,
        _next_segment,
    ) in _shadow_segment_scope_bounds(
        query
    ):
        if (
            next_segment_index
            > current_segment_index
        ):
            next_segment_start = next_start
            break

    nearby_text = query[
        left_scope_start:next_segment_start
    ]

    if not _SHADOW_ROLE_HEAD_PATTERN.search(
        segment_text
    ):
        return ClauseRole.UNKNOWN

    if not _SHADOW_ROLE_CONTEXT_PATTERN.search(
        nearby_text
    ):
        return ClauseRole.UNKNOWN

    return ClauseRole.ROLE


def _shadow_structural_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    segment_index: Optional[int] = None,
) -> ClauseRole:
    """
    L2.7a.6g composite shadow role policy.

    Precedence:

        bounded ROLE construction
        > non-GOAL cue scope
        > contextual ROLE morphology
        > generic GOAL cue
        > UNKNOWN
    """
    bounded_role = (
        _shadow_bounded_role_for_occurrence(
            query,
            char_span=char_span,
        )
    )

    if bounded_role != ClauseRole.UNKNOWN:
        return bounded_role

    cue_role = (
        _shadow_segment_bounded_role_for_occurrence(
            query,
            char_span=char_span,
        )
    )

    # Specialized grammatical cues are stronger than weak
    # occupational morphology.
    #
    # Examples:
    #
    #   I know software engineering
    #       -> SKILL_HELD
    #
    #   I want to learn software engineering
    #       -> SKILL_TARGET
    #
    #   I want to use Python
    #       -> STACK_PREFERENCE
    #
    # ROLE cues such as "targeting" / "become" also remain
    # authoritative.
    #
    # Generic GOAL cues are handled separately below because
    # nearby career framing + an occupational head can provide a
    # more specific interpretation:
    #
    #   need project for job maybe ml engineer
    #
    # Here "need" opens a broad GOAL scope, while
    # "job" + "engineer" provide the narrower ROLE reading.
    if cue_role not in {
        ClauseRole.UNKNOWN,
        ClauseRole.GOAL,
    }:
        return cue_role

    morphology_role = (
        _shadow_role_morphology_for_occurrence(
            query,
            char_span=char_span,
            segment_index=segment_index,
        )
    )

    # Contextual career-role evidence may override only a generic
    # GOAL scope. It must never override SKILL_HELD,
    # SKILL_TARGET, STACK_PREFERENCE, or explicit ROLE cues.
    if (
        morphology_role
        != ClauseRole.UNKNOWN
    ):
        return morphology_role

    if cue_role == ClauseRole.GOAL:
        return ClauseRole.GOAL

    return ClauseRole.UNKNOWN



# =========================================================
# L2.7a.6a — SHADOW CUE-SCOPE ROLE MODEL
#
# This is intentionally diagnostic-only.
#
# Candidate identity must never determine grammatical role.
# Roles come only from cue positions and query structure.
#
# The nearest valid PRECEDING cue owns the following scope.
# A later cue changes that scope.
# Contrast / sentence resets terminate inherited scope.
# =========================================================


_SHADOW_ROLE_CUE_PATTERNS = (
    # -----------------------------------------------------
    # SKILL_HELD
    #
    # Longer constructions intentionally come before generic
    # "with" so that:
    #
    #   comfortable with Python
    #   worked with React
    #
    # do not become STACK_PREFERENCE.
    # -----------------------------------------------------
    (
        re.compile(
            r"\b(?:am\s+|i'm\s+|im\s+)?"
            r"comfortable\s+with\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "comfortable_with",
    ),
    (
        re.compile(
            r"\b(?:am\s+|i'm\s+|im\s+)?"
            r"familiar\s+with\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "familiar_with",
    ),
    (
        re.compile(
            r"\b(?:have\s+)?experience\s+with\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "experience_with",
    ),
    (
        re.compile(
            r"\bworked\s+with\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "worked_with",
    ),
    (
        re.compile(
            r"\bhave\s+used\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "have_used",
    ),
    (
        re.compile(
            r"\bknow\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "know",
    ),
    (
        re.compile(
            r"\bused\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_HELD,
        "used",
    ),

    # -----------------------------------------------------
    # SKILL_TARGET
    # -----------------------------------------------------
    (
        re.compile(
            r"\b(?:want\s+to\s+)?learn\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_TARGET,
        "learn",
    ),
    (
        re.compile(
            r"\bpractice\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_TARGET,
        "practice",
    ),
    (
        re.compile(
            r"\bimprove\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_TARGET,
        "improve",
    ),
    (
        re.compile(
            r"\bteaches?\b",
            re.IGNORECASE,
        ),
        ClauseRole.SKILL_TARGET,
        "teach",
    ),

    # -----------------------------------------------------
    # ROLE / CAREER TARGET
    # -----------------------------------------------------
    (
        re.compile(
            r"\btarget(?:ing)?\b",
            re.IGNORECASE,
        ),
        ClauseRole.ROLE,
        "targeting",
    ),
    (
        re.compile(
            r"\bbecome\b",
            re.IGNORECASE,
        ),
        ClauseRole.ROLE,
        "become",
    ),

    # -----------------------------------------------------
    # STACK PREFERENCE
    # -----------------------------------------------------
    (
        re.compile(
            r"\busing\b",
            re.IGNORECASE,
        ),
        ClauseRole.STACK_PREFERENCE,
        "using",
    ),
    (
        re.compile(
            r"\buses\b",
            re.IGNORECASE,
        ),
        ClauseRole.STACK_PREFERENCE,
        "uses",
    ),
    (
        re.compile(
            r"\buse\b",
            re.IGNORECASE,
        ),
        ClauseRole.STACK_PREFERENCE,
        "use",
    ),
    (
        re.compile(
            r"\bwith\b",
            re.IGNORECASE,
        ),
        ClauseRole.STACK_PREFERENCE,
        "with",
    ),

    # -----------------------------------------------------
    # GOAL
    #
    # These are intentionally after more-specific constructions
    # such as "want to learn".
    # -----------------------------------------------------
    (
        re.compile(
            r"\bwant\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "want",
    ),
    (
        re.compile(
            r"\bneed\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "need",
    ),
    (
        re.compile(
            r"\bbuild\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "build",
    ),
    (
        re.compile(
            r"\bcreate\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "create",
    ),
    (
        re.compile(
            r"\bmake\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "make",
    ),
    (
        re.compile(
            r"\bdevelop\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "develop",
    ),
)


# These close an inherited cue scope when no newer cue has
# explicitly opened another one.
#
# Comma and "and" are deliberately NOT included:
#
#   I know React, Python and TypeScript
#
# should remain one SKILL_HELD scope.
_SHADOW_ROLE_SCOPE_RESET = re.compile(
    r"""
    [;.!?]
    |
    \bbut\b
    |
    \bhowever\b
    |
    \balthough\b
    |
    \bthough\b
    |
    \bwhereas\b
    |
    \bnow\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _shadow_role_cue_occurrences(
    query: str,
):
    """
    Return non-overlapping grammatical cue occurrences.

    Identity of technical concepts is never inspected here.

    Output tuples:

        (
            start,
            end,
            ClauseRole,
            cue_name,
        )
    """
    found = []

    for (
        pattern,
        role,
        cue_name,
    ) in _SHADOW_ROLE_CUE_PATTERNS:
        for match in pattern.finditer(query):
            found.append(
                (
                    match.start(),
                    match.end(),
                    role,
                    cue_name,
                )
            )

    # Earlier position first; at an equal start prefer the
    # longest construction so "comfortable with" owns the
    # occurrence rather than nested "with".
    found.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    result = []

    for item in found:
        start, end, _, _ = item

        overlaps_existing = any(
            (
                start < existing_end
                and end > existing_start
            )
            for (
                existing_start,
                existing_end,
                _,
                _,
            ) in result
        )

        if overlaps_existing:
            continue

        result.append(item)

    return result


def _shadow_cue_scope_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    left_scope_start: int = 0,
) -> ClauseRole:
    """
    Diagnostic L2.7a.6 role assignment.

    Rule:
      nearest valid preceding cue owns the candidate until
      another cue changes the scope or a reset closes it.

    No candidate vocabulary or evidence is consulted.
    """
    if char_span is None:
        return ClauseRole.UNKNOWN

    candidate_start, _ = char_span

    preceding = [
        cue
        for cue in _shadow_role_cue_occurrences(
            query
        )
        if (
            cue[0] >= left_scope_start
            and cue[1] <= candidate_start
        )
    ]

    if not preceding:
        return ClauseRole.UNKNOWN

    # Nearest preceding cue wins.
    cue_start, cue_end, role, _ = max(
        preceding,
        key=lambda item: (
            item[1],
            item[0],
        ),
    )

    between = query[
        cue_end:candidate_start
    ]

    if _SHADOW_ROLE_SCOPE_RESET.search(
        between
    ):
        return ClauseRole.UNKNOWN

    return role


def _shadow_segment_scope_bounds(
    query: str,
):
    """
    Return candidate-segment intervals together with the left
    boundary from which cues are allowed to govern that segment.

    A cue before the previous segment end cannot leak into the
    current segment.
    """
    segments = _candidate_segments(query)

    result = []
    previous_end = 0

    for segment_index, segment in enumerate(
        segments
    ):
        if not segment:
            continue

        start = segment[0].char_span[0]
        end = segment[-1].char_span[1]

        result.append(
            (
                segment_index,
                previous_end,
                start,
                end,
                segment,
            )
        )

        previous_end = end

    return result


def _shadow_segment_bounded_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
) -> ClauseRole:
    """
    L2.7a.6b shadow role assignment.

    Candidate role comes from the latest preceding cue inside
    the candidate's own segment-local left scope.
    """
    if char_span is None:
        return ClauseRole.UNKNOWN

    start, end = char_span

    for (
        _segment_index,
        left_scope_start,
        segment_start,
        segment_end,
        _segment,
    ) in _shadow_segment_scope_bounds(
        query
    ):
        if (
            start >= segment_start
            and end <= segment_end
        ):
            return _shadow_cue_scope_role_for_occurrence(
                query,
                char_span=char_span,
                left_scope_start=left_scope_start,
            )

    return ClauseRole.UNKNOWN


def _shadow_cue_scope_trace(
    query: str,
):
    """
    Small diagnostic helper for L2.7a.6a tests.
    """
    return [
        {
            "cue": cue_name,
            "role": role.value,
            "char_span": (
                start,
                end,
            ),
            "raw": query[start:end],
        }
        for (
            start,
            end,
            role,
            cue_name,
        ) in _shadow_role_cue_occurrences(
            query
        )
    ]


def _best_clause_role_for_span(
    span: str,
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ] = None,
    constituent_char_spans: tuple[
        tuple[int, int],
        ...
    ] = tuple(),
) -> ClauseRole:
    structure = understand_query_structure(
        query
    )

    span_tokens = _surface_tokens(span)

    if not span_tokens:
        return ClauseRole.UNKNOWN

    candidates = [
        candidate
        for candidate in structure.candidates
        if candidate.normalized_form
    ]

    normalized_span = _normalize_span(
        span
    )

    # -----------------------------------------------------
    # OCCURRENCE-AWARE PATH
    #
    # Once exact provenance exists, role inference is local
    # to this occurrence only. An equal surface form elsewhere
    # in the query must not donate its role.
    # -----------------------------------------------------
    if char_span is not None:
        # Exact structural phrase over the same interval wins.
        for candidate in candidates:
            if (
                candidate.normalized_form
                == normalized_span
                and candidate.char_span
                == char_span
            ):
                return candidate.clause_role

        occurrence_roles = []

        for constituent_span in (
            constituent_char_spans
        ):
            for candidate in candidates:
                if (
                    candidate.char_span
                    == constituent_span
                ):
                    occurrence_roles.append(
                        candidate.clause_role
                    )

        non_unknown = {
            role
            for role in occurrence_roles
            if role != ClauseRole.UNKNOWN
        }

        if len(non_unknown) == 1:
            return next(
                iter(non_unknown)
            )

        if not non_unknown:
            return ClauseRole.UNKNOWN

        priority = (
            ClauseRole.ROLE,
            ClauseRole.GOAL,
            ClauseRole.SKILL_TARGET,
            ClauseRole.SKILL_HELD,
            ClauseRole.STACK_PREFERENCE,
        )

        for role in priority:
            if role in non_unknown:
                return role

        return ClauseRole.UNKNOWN

    # -----------------------------------------------------
    # LEGACY TEXT-ONLY PATH
    #
    # Preserve direct callers that do not yet provide
    # occurrence provenance.
    # -----------------------------------------------------

    for candidate in candidates:
        if (
            candidate.normalized_form
            == normalized_span
        ):
            return candidate.clause_role

    matching_roles = []

    span_token_set = set(span_tokens)

    for candidate in candidates:
        candidate_tokens = set(
            candidate.normalized_form.split()
        )

        if (
            candidate_tokens
            and candidate_tokens.issubset(
                span_token_set
            )
        ):
            matching_roles.append(
                candidate.clause_role
            )

    non_unknown = {
        role
        for role in matching_roles
        if role != ClauseRole.UNKNOWN
    }

    if len(non_unknown) == 1:
        return next(
            iter(non_unknown)
        )

    priority = (
        ClauseRole.ROLE,
        ClauseRole.GOAL,
        ClauseRole.SKILL_TARGET,
        ClauseRole.SKILL_HELD,
        ClauseRole.STACK_PREFERENCE,
        ClauseRole.UNKNOWN,
    )

    for role in priority:
        if role in matching_roles:
            return role

    return ClauseRole.UNKNOWN


def resolve_concept_span(
    span: str,
    *,
    query: str,
    top_k: int = 6,
    ambiguity_margin_floor: float = 0.20,
    resolved_min_lexical_hits: int = 3,
    resolved_min_source_types: int = 2,
    char_span: Optional[tuple[int, int]] = None,
    constituent_char_spans: tuple[
        tuple[int, int],
        ...
    ] = tuple(),
    segment_index: Optional[int] = None,
) -> ResolvedConceptSpan:
    all_hits = _collect_span_evidence(
        span,
        top_k=top_k,
    )

    lexical_hits = (
        _lexically_supported_hits(
            all_hits
        )
    )

    # Literal corpus support establishes that the concept exists.
    #
    # Only taxonomy-classified evidence is allowed to determine
    # focus/family. This prevents taxonomy coverage gaps from
    # turning real concepts into fabricated/unresolved concepts.
    domain_hits = [
        hit
        for hit in lexical_hits
        if hit.family != "general"
    ]

    lexical_source_types = {
        hit.source_type
        for hit in lexical_hits
    }

    domain_source_types = {
        hit.source_type
        for hit in domain_hits
    }

    top_bm25_values = [
        hit.bm25_score
        for hit in lexical_hits
        if (
            hit.source_type
            == "research_paper"
            and hit.bm25_score
            is not None
            and hit.bm25_score > 0.0
        )
    ]

    top_bm25_score = (
        max(top_bm25_values)
        if top_bm25_values
        else None
    )

    max_lexical_coverage = (
        max(
            (
                hit.lexical_coverage
                for hit in all_hits
            ),
            default=0.0,
        )
    )

    # -----------------------------------------------------
    # CRITICAL GATE
    #
    # If Solvyn cannot establish literal corpus support,
    # domain inference does not run at all.
    # -----------------------------------------------------
    if not lexical_hits:
        return ResolvedConceptSpan(
            surface_form=span,
            normalized_form=_normalize_span(
                span
            ),
            clause_role=(
                _best_clause_role_for_span(
                    span,
                    query,
                    char_span=char_span,
                    constituent_char_spans=(
                        constituent_char_spans
                    ),
                )
            ),
            ngram_size=len(
                _surface_tokens(span)
            ),
            resolution_status=(
                ResolutionStatus.UNRESOLVED
            ),
            confidence=0.0,
            inferred_focus=None,
            inferred_family=None,
            domain_margin=0.0,
            support_count=0,
            source_type_count=0,
            lexical_support_count=0,
            lexical_source_type_count=0,
            lexical_coverage=round(
                max_lexical_coverage,
                4,
            ),
            top_bm25_score=top_bm25_score,
            supporting_evidence=tuple(),
            char_span=char_span,
            constituent_char_spans=(
                constituent_char_spans
            ),
            segment_index=segment_index,
        )

    # Only lexically supported AND taxonomy-classified evidence
    # may influence concept-domain inference.
    family_scores = _domain_scores(
        domain_hits
    )

    focus_scores = _focus_scores(
        domain_hits
    )

    best_family, family_margin = (
        _best_and_margin(
            family_scores
        )
    )

    best_focus, _ = _best_and_margin(
        focus_scores
    )

    source_types = {
        hit.source_type
        for hit in lexical_hits
    }

    # Confidence describes the inferred domain classification,
    # not merely whether the surface concept exists.
    #
    # Literal-but-unclassified evidence contributes to existence
    # support, but must not inflate confidence in a domain it
    # cannot classify.
    confidence = _confidence(
        hits=domain_hits,
        margin=family_margin,
    )

    # Existence authority and domain-classification authority
    # are intentionally different.
    #
    # Literal but taxonomy-unclassified evidence may prove that
    # a concept exists, but it must not strengthen a particular
    # inferred domain.
    has_resolution_authority = (
        len(domain_hits)
        >= resolved_min_lexical_hits
        and len(domain_source_types)
        >= resolved_min_source_types
    )

    if not has_resolution_authority:
        status = ResolutionStatus.SUPPORTED_WEAK

    elif best_family is None:
        # Strong literal support can exist without enough
        # classified evidence to name a domain.
        status = ResolutionStatus.SUPPORTED_WEAK

    elif len(family_scores) == 1:
        # Domain authority is strong and all classified evidence
        # supports the same family. There is no competing family
        # against which a margin can be measured.
        status = ResolutionStatus.EVIDENCE_RESOLVED

    elif family_margin >= ambiguity_margin_floor:
        status = ResolutionStatus.EVIDENCE_RESOLVED

    else:
        status = ResolutionStatus.SUPPORTED_AMBIGUOUS

    return ResolvedConceptSpan(
        surface_form=span,
        normalized_form=_normalize_span(
            span
        ),
        clause_role=(
            _best_clause_role_for_span(
                span,
                query,
                char_span=char_span,
                constituent_char_spans=(
                    constituent_char_spans
                ),
            )
        ),
        ngram_size=len(
            _surface_tokens(span)
        ),
        resolution_status=status,
        confidence=confidence,
        inferred_focus=best_focus,
        inferred_family=best_family,
        domain_margin=family_margin,
        support_count=len(
            lexical_hits
        ),
        source_type_count=len(
            source_types
        ),
        lexical_support_count=len(
            lexical_hits
        ),
        lexical_source_type_count=len(
            lexical_source_types
        ),
        lexical_coverage=round(
            max_lexical_coverage,
            4,
        ),
        top_bm25_score=top_bm25_score,
        supporting_evidence=tuple(
            lexical_hits[:12]
        ),
        char_span=char_span,
        constituent_char_spans=(
            constituent_char_spans
        ),
        segment_index=segment_index,
    )


def resolve_query_spans_shadow(
    query: str,
    *,
    max_n: int = 4,
    top_k: int = 6,
) -> List[ResolvedConceptSpan]:
    spans = generate_structured_ngram_spans(
        query,
        max_n=max_n,
    )

    resolved = [
        resolve_concept_span(
            span.surface_form,
            query=query,
            top_k=top_k,
            char_span=span.char_span,
            constituent_char_spans=(
                span.constituent_char_spans
            ),
            segment_index=span.segment_index,
        )
        for span in spans
    ]

    status_priority = {
        ResolutionStatus.EVIDENCE_RESOLVED: 3,
        ResolutionStatus.SUPPORTED_AMBIGUOUS: 2,
        ResolutionStatus.SUPPORTED_WEAK: 1,
        ResolutionStatus.UNRESOLVED: 0,
    }

    return sorted(
        resolved,
        key=lambda item: (
            status_priority[
                item.resolution_status
            ],
            item.confidence,
            item.domain_margin,
            item.ngram_size,
        ),
        reverse=True,
    )
