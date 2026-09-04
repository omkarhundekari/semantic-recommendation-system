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
from lexical_equivalence import (
    get_lexically_equivalent_forms,
)
from project_corpus_search import (
    search_project_corpus,
)
from query_concept_understanding import (
    ClauseRole,
    LexicalConceptCandidate,
    extract_lexical_concept_candidates,
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

    # Stable record identity when the upstream source exposes one.
    #
    # Synthetic and legacy callers may omit this field; authority
    # accounting then falls back to source type + normalized title.
    evidence_id: Optional[str] = None


@dataclass(frozen=True)
class GeneratedConceptSpan:
    surface_form: str
    normalized_form: str
    clause_role: ClauseRole

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


def _literal_lexical_coverage(
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


def _lexical_coverage(
    surface_form: str,
    item: Dict,
) -> float:
    """
    Report the strongest literal coverage across equivalent forms.

    Coverage therefore remains lexical rather than domain-derived.
    """
    equivalents = get_lexically_equivalent_forms(
        surface_form
    )

    if not equivalents:
        return 0.0

    return max(
        _literal_lexical_coverage(
            equivalent,
            item,
        )
        for equivalent in equivalents
    )


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


def _literal_lexical_match(
    surface_form: str,
    item: Dict,
) -> bool:
    """
    Match one literal surface form without semantic expansion.
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


def _lexical_match(
    surface_form: str,
    item: Dict,
) -> bool:
    """
    Qualify evidence against strict lexical equivalents.

    Equivalence expands surface matching only. It does not assign
    a family, focus, score, status, or semantic authority.
    """
    return any(
        _literal_lexical_match(
            equivalent,
            item,
        )
        for equivalent in get_lexically_equivalent_forms(
            surface_form
        )
    )


def _normalized_evidence_title(
    title: str,
) -> str:
    return " ".join(
        str(title or "").strip().lower().split()
    )


def _evidence_identity_from_item(
    item: Dict,
    *,
    source_type: str,
) -> str:
    title = str(
        item.get("title", "")
        or item.get("name", "")
        or ""
    )

    if source_type == "research_paper":
        document_id = str(
            item.get("document_id", "")
            or ""
        ).strip()

        if document_id:
            return (
                f"research_paper:{document_id}"
            )

    if source_type == "github_repository":
        url = str(
            item.get("url", "")
            or ""
        ).strip().lower()

        if url:
            return (
                f"github_repository:{url}"
            )

    # Project-pattern titles already act as source identifiers
    # elsewhere in the corpus. This fallback also supplies stable
    # identity for direct/synthetic ConceptEvidenceHit callers.
    return (
        f"{source_type}:"
        f"{_normalized_evidence_title(title)}"
    )


def _evidence_identity(
    hit: ConceptEvidenceHit,
) -> str:
    if hit.evidence_id:
        return hit.evidence_id

    return (
        f"{hit.source_type}:"
        f"{_normalized_evidence_title(hit.title)}"
    )


def _deduplicate_evidence_hits(
    hits: Sequence[ConceptEvidenceHit],
) -> List[ConceptEvidenceHit]:
    by_identity: Dict[
        str,
        ConceptEvidenceHit,
    ] = {}

    conflicted_identities: set[str] = set()
    order: List[str] = []

    for hit in hits:
        identity = _evidence_identity(hit)

        if identity in conflicted_identities:
            continue

        previous = by_identity.get(
            identity
        )

        if previous is None:
            order.append(identity)
            by_identity[identity] = hit
            continue

        semantic_identity = (
            hit.family,
            hit.focus,
        )
        previous_semantic_identity = (
            previous.family,
            previous.focus,
        )

        if (
            semantic_identity
            != previous_semantic_identity
        ):
            # One canonical evidence record cannot vote for
            # contradictory semantic classifications.
            #
            # Retrieval score is not semantic authority. Once two
            # representations of one identity disagree on family or
            # focus, fail closed by removing that identity from
            # classification support entirely.
            conflicted_identities.add(
                identity
            )
            by_identity.pop(
                identity,
                None,
            )
            continue

        # Repeated retrieval of one semantically consistent record
        # contributes once. Preserve the strongest retrieval
        # representation without increasing support multiplicity.
        if hit.score > previous.score:
            by_identity[identity] = hit

    return [
        by_identity[identity]
        for identity in order
        if identity in by_identity
    ]


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
        evidence_id=_evidence_identity_from_item(
            item,
            source_type=source_type,
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


def _source_capped_scores(
    hits: Sequence[ConceptEvidenceHit],
    *,
    label_attribute: str,
) -> Dict[str, float]:
    """
    Aggregate competing semantic labels with one vote ceiling per
    source type.

    Distinct records remain available to absolute authority/support
    accounting. This function controls only candidate election, so
    repeated retrieval from one provenance class cannot gain
    unbounded voting weight.
    """
    by_label: Dict[str, Dict[str, float]] = {}

    for hit in hits:
        label = getattr(
            hit,
            label_attribute,
        )

        label_bucket = by_label.setdefault(
            label,
            {},
        )

        previous = label_bucket.get(
            hit.source_type,
            0.0,
        )

        label_bucket[hit.source_type] = max(
            previous,
            max(hit.score, 0.0001),
        )

    return {
        label: sum(source_scores.values())
        for label, source_scores in by_label.items()
    }


def _domain_scores(
    hits: Sequence[ConceptEvidenceHit],
) -> Dict[str, float]:
    return _source_capped_scores(
        hits,
        label_attribute="family",
    )


def _focus_authority_hits(
    hits: Sequence[ConceptEvidenceHit],
) -> List[ConceptEvidenceHit]:
    """
    Keep only evidence that explicitly asserts its canonical focus.

    A category translated through a broader upstream taxonomy may
    still support family classification, but that translation does
    not automatically become focus-level authority.
    """
    qualified = []

    for hit in hits:
        category = (
            str(hit.category or "")
            .strip()
            .lower()
            .replace("-", "_")
        )
        focus = (
            str(hit.focus or "")
            .strip()
            .lower()
            .replace("-", "_")
        )

        if category == focus:
            qualified.append(hit)

    return qualified


def _focus_scores(
    hits: Sequence[ConceptEvidenceHit],
) -> Dict[str, float]:
    return _source_capped_scores(
        _focus_authority_hits(hits),
        label_attribute="focus",
    )


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
) -> List[LexicalConceptCandidate]:
    return sorted(
        extract_lexical_concept_candidates(
            query
        ),
        key=lambda candidate: (
            candidate.char_span[0],
            candidate.char_span[1],
        ),
    )


def _has_hard_boundary(
    query: str,
    left: LexicalConceptCandidate,
    right: LexicalConceptCandidate,
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
) -> List[List[LexicalConceptCandidate]]:
    candidates = _candidate_tokens(query)

    if not candidates:
        return []

    segments: List[List[LexicalConceptCandidate]] = []
    current: List[LexicalConceptCandidate] = []
    previous_valid: Optional[LexicalConceptCandidate] = None

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


def _candidate_cohesive_runs(
    query: str,
    candidates: List[LexicalConceptCandidate],
) -> List[List[LexicalConceptCandidate]]:
    """
    Partition supplied candidate occurrences by raw-text cohesion.

    Candidates remain in the same run only when the text between
    their source occurrences contains whitespace and nothing else.
    This observes omission boundaries; it does not infer syntax.
    """
    if not candidates:
        return []

    runs: List[List[LexicalConceptCandidate]] = []
    current = [candidates[0]]

    for left, right in zip(
        candidates,
        candidates[1:],
    ):
        gap = query[
            left.char_span[1]:
            right.char_span[0]
        ]

        if gap and not gap.isspace():
            runs.append(current)
            current = [right]
            continue

        current.append(right)

    runs.append(current)
    return runs


def _valid_candidate(
    candidate: LexicalConceptCandidate,
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
                group_roles = [
                    _structural_role_for_occurrence(
                        query,
                        char_span=candidate.char_span,
                        segment_index=segment_index,
                    )
                    for candidate in group
                ]

                roles = {
                    role
                    for role in group_roles
                    if role
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

                clause_role = (
                    _structural_role_for_occurrence(
                        query,
                        char_span=char_span,
                        segment_index=segment_index,
                    )
                )

                spans.append(
                    GeneratedConceptSpan(
                        surface_form=surface,
                        normalized_form=normalized,
                        clause_role=clause_role,
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


# Tokens that invalidate a supposedly bounded ``for ... role``
# construction.
#
# A ROLE construction is allowed to contain an open-class role
# description, but it must not cross into a subordinate clause,
# stack phrase, infinitive, contrast, or another structural
# relation.
#
# Example that must NOT become one ROLE span:
#
#     for React that helps with data roles
#
# The old bounded regex could consume:
#
#     React that helps with data
#
# simply because a later ``roles`` token existed.  That is a
# greedy-extent failure inside an otherwise closed construction.
#
# We therefore constrain the interior grammar rather than tuning
# an arbitrary token-count limit.
_BOUNDED_ROLE_INTERIOR_BLOCKERS = (
    "that",
    "which",
    "who",
    "whom",
    "whose",
    "with",
    "using",
    "use",
    "uses",
    "to",
    "by",
    "but",
    "however",
    "although",
    "though",
    "whereas",
)


_BOUNDED_ROLE_BLOCKER_PATTERN = (
    "|".join(
        re.escape(token)
        for token in _BOUNDED_ROLE_INTERIOR_BLOCKERS
    )
)


_BOUNDED_ROLE_PATTERNS = (
    # Example:
    #
    #   I want something for a data engineer role.
    #
    # Both edges are explicit:
    #
    #   for  ........  role
    #
    # and the interior is forbidden from crossing a known
    # structural relation.  This preserves open-class role names
    # without allowing an unrelated relative clause to be
    # swallowed by the construction.
    re.compile(
        r"\bfor\s+"
        r"(?:an?\s+|the\s+)?"
        r"("
        r"(?:(?!\b(?:"
        + _BOUNDED_ROLE_BLOCKER_PATTERN
        + r")\b)"
        r"[A-Za-z][A-Za-z0-9+#.-]*"
        r"(?:\s+|(?=\s+roles?\b))"
        r")+?"
        r")"
        r"\s*roles?\b",
        re.IGNORECASE,
    ),
)


# Occupational heads are a deliberately small closed-class
# grammatical/morphological signal, not an open-world dictionary
# of job titles.
_ROLE_HEAD_PATTERN = re.compile(
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
_ROLE_CONTEXT_PATTERN = re.compile(
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


def _bounded_role_spans(
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
        _BOUNDED_ROLE_PATTERNS
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


def _bounded_role_for_occurrence(
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
    ) in _bounded_role_spans(
        query
    ):
        if (
            start >= role_start
            and end <= role_end
        ):
            return ClauseRole.ROLE

    return ClauseRole.UNKNOWN


def _role_morphology_for_occurrence(
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

      * the candidate must end at the segment's occupational
        head, or be immediately followed by that terminal head;
        and
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
    ) in _segment_scope_bounds(
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

    candidate_text = query[
        start:end
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
    ) in _segment_scope_bounds(
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

    # -----------------------------------------------------
    # TERMINAL OCCUPATIONAL-HEAD LOCALITY
    #
    # Career morphology must not leak from an occupational
    # word elsewhere in the same candidate segment.
    #
    # Bad:
    #
    #   want a data scientist dashboard for my job
    #
    # ``scientist`` is role-shaped, but ``dashboard`` is the
    # actual terminal concept and must remain GOAL.
    #
    # Good:
    #
    #   cybersecurity analyst portfolio
    #   need project for job maybe ml engineer
    #
    # In those cases the occupational head is the terminal head
    # of the segment.
    #
    # A candidate therefore receives morphology ROLE only when:
    #
    #   1. it itself ends in the occupational head AND reaches
    #      the end of the candidate segment; or
    #
    #   2. it is a modifier immediately followed by the
    #      occupational head, and that head reaches the end of
    #      the candidate segment.
    #
    # This preserves constituent role propagation such as
    # ``ml`` -> ROLE in ``ml engineer`` without allowing a
    # preceding ``scientist`` to contaminate ``dashboard``.
    # -----------------------------------------------------

    candidate_head_matches = list(
        _ROLE_HEAD_PATTERN.finditer(
            candidate_text
        )
    )

    candidate_ends_with_terminal_head = (
        end == segment_end
        and bool(candidate_head_matches)
        and candidate_head_matches[-1].end()
        == len(candidate_text)
    )

    right_tail = query[
        end:segment_end
    ]

    right_tail_stripped = (
        right_tail.lstrip()
    )

    right_head_match = (
        _ROLE_HEAD_PATTERN.match(
            right_tail_stripped
        )
    )

    right_adjacent_terminal_head = False

    if right_head_match is not None:
        leading_whitespace = (
            len(right_tail)
            - len(right_tail_stripped)
        )

        absolute_head_end = (
            end
            + leading_whitespace
            + right_head_match.end()
        )

        right_adjacent_terminal_head = (
            absolute_head_end
            == segment_end
        )

    if not (
        candidate_ends_with_terminal_head
        or right_adjacent_terminal_head
    ):
        return ClauseRole.UNKNOWN

    if not _ROLE_CONTEXT_PATTERN.search(
        nearby_text
    ):
        return ClauseRole.UNKNOWN

    return ClauseRole.ROLE



_TERSE_NOMINAL_REQUEST_HEADS = frozenset(
    {
        "project",
    }
)


def _terse_nominal_goal_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    segment_index: Optional[int] = None,
) -> ClauseRole:
    """
    Weak GOAL fallback for a terminal nominal project request.

    The structural project head is filtered from concept
    candidates, so this rule relates raw query framing to the
    canonical candidate segment without using concept identity or
    evidence.
    """
    if char_span is None:
        return ClauseRole.UNKNOWN

    start, end = char_span
    segment_bounds = _segment_scope_bounds(
        query
    )

    matched_position = None
    matched_bounds = None

    for position, bounds in enumerate(
        segment_bounds
    ):
        (
            current_segment_index,
            _current_left_scope_start,
            current_segment_start,
            current_segment_end,
            _segment,
        ) = bounds

        if not (
            start >= current_segment_start
            and end <= current_segment_end
        ):
            continue

        if (
            segment_index is not None
            and current_segment_index
            != segment_index
        ):
            continue

        matched_position = position
        matched_bounds = bounds
        break

    if (
        matched_position is None
        or matched_bounds is None
    ):
        return ClauseRole.UNKNOWN

    (
        _matched_segment_index,
        left_scope_start,
        segment_start,
        segment_end,
        _matched_segment,
    ) = matched_bounds

    cohesive_runs = _candidate_cohesive_runs(
        query,
        _matched_segment,
    )

    # This fallback is intentionally weaker than explicit role
    # cues. Omitted raw material inside the candidate segment
    # means the nominal-project reading is not structurally
    # strong enough to assign GOAL.
    if len(cohesive_runs) != 1:
        return ClauseRole.UNKNOWN

    left_frame = query[
        left_scope_start:segment_start
    ]

    # Remove only an established sentence/contrast role reset.
    # Candidate boundaries such as "for", "with", and "using"
    # are not equivalent to clause resets.
    reset_matches = list(
        _ROLE_SCOPE_RESET.finditer(
            left_frame
        )
    )

    if reset_matches:
        last_reset = reset_matches[-1]

        if not left_frame[
            :last_reset.start()
        ].strip():
            left_frame = left_frame[
                last_reset.end():
            ]

    left_tokens = [
        match.group(0).lower()
        for match in TOKEN_PATTERN.finditer(
            left_frame
        )
    ]

    bare_nominal_frame = (
        left_tokens
        in (
            [],
            ["a"],
            ["an"],
            ["the"],
        )
    )

    if not bare_nominal_frame:
        relational_frame = (
            left_tokens
            in (
                ["for"],
                ["for", "a"],
                ["for", "an"],
                ["for", "the"],
            )
        )

        if (
            not relational_frame
            or matched_position == 0
        ):
            return ClauseRole.UNKNOWN

        (
            _previous_segment_index,
            previous_left_scope_start,
            _previous_segment_start,
            _previous_segment_end,
            previous_segment,
        ) = segment_bounds[
            matched_position - 1
        ]

        if not previous_segment:
            return ClauseRole.UNKNOWN

        previous_occurrence = (
            previous_segment[-1]
        )

        previous_cue_role = (
            _cue_scope_role_for_occurrence(
                query,
                char_span=(
                    previous_occurrence.char_span
                ),
                left_scope_start=(
                    previous_left_scope_start
                ),
            )
        )

        if (
            previous_cue_role
            != ClauseRole.STACK_PREFERENCE
        ):
            return ClauseRole.UNKNOWN

    # Punctuation outside an established reset is not part of the
    # accepted nominal or stack-complement frame.
    residual_left = TOKEN_PATTERN.sub(
        "",
        left_frame,
    ).strip()

    if residual_left:
        return ClauseRole.UNKNOWN

    right_tail = query[
        segment_end:
    ]

    raw_tokens = list(
        TOKEN_PATTERN.finditer(
            right_tail
        )
    )

    if not raw_tokens:
        return ClauseRole.UNKNOWN

    head_match = raw_tokens[0]

    # The structural head must immediately follow the candidate
    # segment apart from whitespace.
    if right_tail[
        :head_match.start()
    ].strip():
        return ClauseRole.UNKNOWN

    if (
        head_match.group(0).lower()
        not in _TERSE_NOMINAL_REQUEST_HEADS
    ):
        return ClauseRole.UNKNOWN

    absolute_head_end = (
        segment_end
        + head_match.end()
    )

    trailing_text = query[
        absolute_head_end:
    ].strip()

    # Only a terminal project head is recognized. Terminal
    # punctuation is harmless; further language makes the weak
    # fallback abstain.
    if (
        trailing_text
        and not re.fullmatch(
            r"[,;.!?:]+",
            trailing_text,
        )
    ):
        return ClauseRole.UNKNOWN

    return ClauseRole.GOAL

def _structural_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    segment_index: Optional[int] = None,
) -> ClauseRole:
    """
    L2.7a structural role policy.

    Precedence:

        bounded ROLE construction
        > non-GOAL cue scope
        > contextual ROLE morphology
        > generic GOAL cue
        > terse nominal request
        > UNKNOWN
    """
    bounded_role = (
        _bounded_role_for_occurrence(
            query,
            char_span=char_span,
        )
    )

    if bounded_role != ClauseRole.UNKNOWN:
        return bounded_role

    cue_role = (
        _segment_bounded_role_for_occurrence(
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
        _role_morphology_for_occurrence(
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

    terse_nominal_role = (
        _terse_nominal_goal_for_occurrence(
            query,
            char_span=char_span,
            segment_index=segment_index,
        )
    )

    if terse_nominal_role != ClauseRole.UNKNOWN:
        return terse_nominal_role

    return ClauseRole.UNKNOWN



# =========================================================
# STRUCTURAL CUE-SCOPE ROLE MODEL
#
# Candidate identity must never determine grammatical role.
# Roles come only from cue positions and query structure.
#
# The nearest valid PRECEDING cue owns the following scope.
# A later cue changes that scope.
# Contrast / sentence resets terminate inherited scope.
# =========================================================


_ROLE_CUE_PATTERNS = (
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
            r"\bteach(?:es)?\b",
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
            r"\blooking\s+for\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "looking_for",
    ),
    (
        re.compile(
            r"\bsearching\s+for\b",
            re.IGNORECASE,
        ),
        ClauseRole.GOAL,
        "searching_for",
    ),
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
_ROLE_SCOPE_RESET = re.compile(
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


def _bounded_seeking_project_cues(
    query: str,
):
    """
    Return structurally bounded ``seeking ... project`` cues.

    This observes candidate positions, raw omission boundaries,
    and the terminal project head only. It does not assign roles
    to candidates or inspect concept identity or evidence.
    """
    cues = []

    for match in re.finditer(
        r"\bseeking\b",
        query,
        re.IGNORECASE,
    ):
        seeking_start = match.start()
        seeking_end = match.end()

        matched_segment = None

        for segment in _candidate_segments(query):
            if any(
                candidate.char_span[0]
                <= seeking_start
                and candidate.char_span[1]
                >= seeking_end
                for candidate in segment
            ):
                matched_segment = segment
                break

        if matched_segment is None:
            continue

        runs = _candidate_cohesive_runs(
            query,
            matched_segment,
        )

        seeking_run_index = None

        for index, run in enumerate(runs):
            if any(
                candidate.char_span[0]
                <= seeking_start
                and candidate.char_span[1]
                >= seeking_end
                for candidate in run
            ):
                seeking_run_index = index
                break

        if seeking_run_index is None:
            continue

        requested_index = seeking_run_index + 1

        if requested_index >= len(runs):
            continue

        requested_run = runs[requested_index]

        # The bounded construction admits only an article between
        # the request verb and requested candidate material.
        gap = query[
            seeking_end:
            requested_run[0].char_span[0]
        ]

        if not re.fullmatch(
            r"\s+(?:a|an|the)\s+",
            gap,
            re.IGNORECASE,
        ):
            continue

        requested_end = (
            requested_run[-1].char_span[1]
        )

        tail = query[requested_end:]

        head_match = re.match(
            r"\s+project\b",
            tail,
            re.IGNORECASE,
        )

        if head_match is None:
            continue

        trailing = tail[
            head_match.end():
        ].strip()

        if (
            trailing
            and not re.fullmatch(
                r"[,;.!?:]+",
                trailing,
            )
        ):
            continue

        cues.append(
            (
                seeking_start,
                seeking_end,
                ClauseRole.GOAL,
                "seeking_project",
            )
        )

    return cues


def _role_cue_occurrences(
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
    found = list(
        _bounded_seeking_project_cues(
            query
        )
    )

    for (
        pattern,
        role,
        cue_name,
    ) in _ROLE_CUE_PATTERNS:
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


def _cue_scope_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
    left_scope_start: int = 0,
) -> ClauseRole:
    """
    Occurrence-aware cue-scope role assignment.

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
        for cue in _role_cue_occurrences(
            query
        )
        if (
            cue[1] <= candidate_start
            and (
                cue[0] >= left_scope_start
                or (
                    cue[0]
                    < left_scope_start
                    < cue[1]
                )
            )
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

    if _ROLE_SCOPE_RESET.search(
        between
    ):
        return ClauseRole.UNKNOWN

    return role


def _segment_scope_bounds(
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


def _segment_bounded_role_for_occurrence(
    query: str,
    *,
    char_span: Optional[
        tuple[int, int]
    ],
) -> ClauseRole:
    """
    Segment-bounded cue-scope role assignment.

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
    ) in _segment_scope_bounds(
        query
    ):
        if (
            start >= segment_start
            and end <= segment_end
        ):
            return _cue_scope_role_for_occurrence(
                query,
                char_span=char_span,
                left_scope_start=left_scope_start,
            )

    return ClauseRole.UNKNOWN


def _role_cue_scope_trace(
    query: str,
):
    """
    Return a diagnostic trace of detected role cues.
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
        ) in _role_cue_occurrences(
            query
        )
    ]


def resolve_concept_span(
    span: str,
    *,
    query: str,
    top_k: int = 6,
    ambiguity_margin_floor: float = 0.20,
    resolved_min_lexical_hits: int = 3,
    char_span: Optional[tuple[int, int]] = None,
    constituent_char_spans: tuple[
        tuple[int, int],
        ...
    ] = tuple(),
    segment_index: Optional[int] = None,
    clause_role: ClauseRole,
) -> ResolvedConceptSpan:
    all_hits = _collect_span_evidence(
        span,
        top_k=top_k,
    )

    lexical_hits = (
        _deduplicate_evidence_hits(
            _lexically_supported_hits(
                all_hits
            )
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
            clause_role=clause_role,
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

    best_family, family_margin = (
        _best_and_margin(
            family_scores
        )
    )

    source_types = {
        hit.source_type
        for hit in lexical_hits
    }

    # Existence authority and domain-classification authority
    # are intentionally different.
    #
    # Literal but taxonomy-unclassified evidence may prove that
    # a concept exists, but it must not strengthen a particular
    # inferred domain.
    #
    # Classification authority must also be attributable to the
    # elected family itself. Evidence supporting competing
    # families may participate in family competition, but must
    # not manufacture authority for the winner.
    winning_family_hits = [
        hit
        for hit in domain_hits
        if hit.family == best_family
    ]

    # Confidence describes the elected domain classification.
    # Its positive support contribution must therefore come only
    # from evidence attributable to that elected family.
    #
    # Competing-family evidence is already represented through
    # family_margin and must not additionally inflate confidence
    # through record count or source-type diversity.
    confidence = _confidence(
        hits=winning_family_hits,
        margin=family_margin,
    )

    # Source diversity is provenance information, not semantic
    # corroboration. Family authority is earned from enough
    # distinct evidence records attributable to the elected family.
    has_resolution_authority = (
        len(winning_family_hits)
        >= resolved_min_lexical_hits
    )

    # Focus specificity is earned separately and hierarchically:
    # only evidence belonging to the elected family may compete.
    focus_authority_hits = _focus_authority_hits(
        winning_family_hits
    )

    # All focus-capable hypotheses remain in candidate election.
    # Focus coherence is distinct from family-level resolution
    # authority: weak evidence may carry a coherent focus, while
    # competing focus hypotheses must still satisfy the ambiguity
    # margin before specificity is reported.
    winning_focus_scores = _focus_scores(
        focus_authority_hits
    )

    best_focus, focus_margin = (
        _best_and_margin(
            winning_focus_scores
        )
    )

    focus_is_coherent = (
        len(winning_focus_scores) == 1
        or (
            len(winning_focus_scores) > 1
            and focus_margin
            >= ambiguity_margin_floor
        )
    )

    if not focus_is_coherent:
        best_focus = None

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
        clause_role=clause_role,
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
            clause_role=span.clause_role,
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
