from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from domain_taxonomy import get_domain_family
from query_concept_resolution import (
    ResolutionStatus,
    ResolvedConceptSpan,
    resolve_query_spans_shadow,
)
from query_concept_understanding import ClauseRole


# =========================================================
# CANONICAL QUERY SEMANTICS
#
# Responsibilities:
#
#   query_concept_understanding
#       -> grammatical candidate structure
#
#   query_concept_resolution
#       -> occurrence-level semantic/evidence resolution
#
#   query_semantics
#       -> query-level selection and aggregation
#
# This module is intentionally the ONLY layer that answers:
#
#   * which resolved occurrences should survive overlap?
#   * which semantic role has primary domain authority?
#   * what canonical focus/family represents the user's intent?
#   * which concepts are useful semantic anchors?
#
# Domain family is always canonicalized through domain_taxonomy.
# Resolver evidence is never allowed to redefine taxonomy.
# =========================================================


@dataclass(frozen=True)
class QuerySemanticSnapshot:
    raw_query: str

    # Every occurrence-level resolver result.
    resolved_spans: Sequence[ResolvedConceptSpan]

    # Overlap-reduced semantic representatives.
    selected_spans: Sequence[ResolvedConceptSpan]

    # Canonical query-level domain.
    #
    # None deliberately means:
    #
    #     "the query does not provide enough structural authority
    #      to name one domain safely."
    #
    # It does NOT mean resolver failure.
    primary_focus: Optional[str]
    primary_family: Optional[str]

    # Human-readable/open-world concepts preserved for downstream
    # planning and generation.
    anchors: Sequence[str]

    # True when structurally authoritative candidates disagree in
    # a way that cannot safely be collapsed to one focus.
    domain_ambiguous: bool


_STATUS_PRIORITY = {
    ResolutionStatus.EVIDENCE_RESOLVED: 3,
    ResolutionStatus.SUPPORTED_AMBIGUOUS: 2,
    ResolutionStatus.SUPPORTED_WEAK: 1,
    ResolutionStatus.UNRESOLVED: 0,
}


# Domain authority is intentionally structural.
#
# Technology mention != project objective.
#
# STACK_PREFERENCE and SKILL_HELD may be excellent anchors but do
# not independently decide the user's project domain.
_DOMAIN_ROLE_PRIORITY = {
    ClauseRole.GOAL: 3,
    ClauseRole.SKILL_TARGET: 2,
    ClauseRole.ROLE: 1,
}


_ANCHOR_ROLE_PRIORITY = {
    ClauseRole.GOAL: 6,
    ClauseRole.SKILL_TARGET: 5,
    ClauseRole.ROLE: 4,
    ClauseRole.STACK_PREFERENCE: 3,
    ClauseRole.SKILL_HELD: 2,
    ClauseRole.UNKNOWN: 1,
    ClauseRole.CONSTRAINT: 0,
}


def _span_bounds(
    span: ResolvedConceptSpan,
) -> Tuple[int, int]:
    return span.char_span or (-1, -1)


def _contains(
    outer: ResolvedConceptSpan,
    inner: ResolvedConceptSpan,
) -> bool:
    if outer.char_span is None or inner.char_span is None:
        return False

    outer_start, outer_end = outer.char_span
    inner_start, inner_end = inner.char_span

    return (
        outer_start <= inner_start
        and outer_end >= inner_end
    )


def _overlaps(
    left: ResolvedConceptSpan,
    right: ResolvedConceptSpan,
) -> bool:
    if left.char_span is None or right.char_span is None:
        return False

    left_start, left_end = left.char_span
    right_start, right_end = right.char_span

    return (
        left_start < right_end
        and right_start < left_end
    )


def _selection_strength(
    span: ResolvedConceptSpan,
):
    """
    Strength used only for overlap reduction.

    Evidence authority comes before phrase length. This prevents
    an unsupported generated n-gram from hiding a strongly
    supported atomic concept.

    Among equally supported readings, the more specific phrase
    wins.
    """
    return (
        _STATUS_PRIORITY[
            span.resolution_status
        ],
        span.ngram_size,
        span.confidence,
        span.domain_margin,
        span.lexical_support_count,
    )


def _select_semantic_spans(
    resolved: Sequence[ResolvedConceptSpan],
) -> List[ResolvedConceptSpan]:
    """
    Remove redundant contained readings conservatively.

    A containing phrase suppresses a smaller occurrence only when:

      * both have the same structural role; and
      * the containing phrase is at least as well supported.

    This means:

        data engineering

    can suppress:

        data
        engineering

    when the phrase itself is strongly resolved.

    But an unresolved:

        cybersecurity analyst

    cannot erase a strongly resolved:

        cybersecurity
    """
    ordered = sorted(
        resolved,
        key=lambda span: (
            span.segment_index
            if span.segment_index is not None
            else 10**9,
            _span_bounds(span)[0],
            -span.ngram_size,
        ),
    )

    selected = []

    for candidate in ordered:
        suppressed = False

        for other in ordered:
            if other is candidate:
                continue

            if (
                other.segment_index
                != candidate.segment_index
            ):
                continue

            if (
                other.clause_role
                != candidate.clause_role
            ):
                continue

            if not _contains(
                other,
                candidate,
            ):
                continue

            if (
                other.char_span
                == candidate.char_span
            ):
                continue

            if (
                _selection_strength(other)
                >= _selection_strength(candidate)
            ):
                suppressed = True
                break

        if not suppressed:
            selected.append(candidate)

    return selected


def _connected_components(
    spans: Sequence[ResolvedConceptSpan],
) -> List[List[ResolvedConceptSpan]]:
    """
    Return overlap-connected components.

    This lets us distinguish:

        AI ... FastAPI

    which occur in separate semantic regions,

    from:

        data / data scientist / dashboard

    where generated overlapping readings disagree inside one
    semantic region.
    """
    remaining = list(spans)
    components = []

    while remaining:
        seed = remaining.pop(0)
        component = [seed]

        changed = True

        while changed:
            changed = False
            survivors = []

            for candidate in remaining:
                if any(
                    _overlaps(
                        candidate,
                        existing,
                    )
                    for existing in component
                ):
                    component.append(
                        candidate
                    )
                    changed = True
                else:
                    survivors.append(
                        candidate
                    )

            remaining = survivors

        components.append(component)

    return components


def _canonical_focus(
    span: ResolvedConceptSpan,
) -> Optional[str]:
    focus = (
        span.inferred_focus or ""
    ).strip()

    if not focus or focus == "general":
        return None

    return focus


def _component_has_domain_conflict(
    component: Sequence[ResolvedConceptSpan],
) -> bool:
    """
    Detect incompatible high-authority interpretations inside one
    overlap-connected semantic region.

    Only EVIDENCE_RESOLVED readings participate in this hard
    conflict check.

    Example:

        want a data scientist dashboard ...

    may independently resolve:

        data       -> data_engineering
        dashboard  -> cloud

    while no supported phrase establishes which interpretation is
    actually intended.

    In that situation we abstain instead of allowing confidence
    alone to manufacture a domain.
    """
    reliable = [
        span
        for span in component
        if (
            span.resolution_status
            == ResolutionStatus.EVIDENCE_RESOLVED
            and _canonical_focus(span)
            is not None
        )
    ]

    focuses = {
        _canonical_focus(span)
        for span in reliable
    }

    focuses.discard(None)

    if len(focuses) <= 1:
        return False

    # A resolved multi-token phrase may legitimately disambiguate
    # its contained atomic readings.
    resolved_phrases = [
        span
        for span in reliable
        if span.ngram_size > 1
    ]

    for phrase in resolved_phrases:
        contained = [
            span
            for span in reliable
            if _contains(
                phrase,
                span,
            )
        ]

        contained_focuses = {
            _canonical_focus(span)
            for span in contained
        }

        contained_focuses.discard(None)

        if len(contained_focuses) >= 2:
            return False

    return True


def _domain_candidates(
    selected: Sequence[ResolvedConceptSpan],
) -> List[ResolvedConceptSpan]:
    """
    Return spans allowed to establish the query-level domain.

    SUPPORTED_WEAK is deliberately excluded.

    Weak lexical evidence is useful for preserving a concept and
    may still appear in anchors, but it is not strong enough to
    steer retrieval, planning, feasibility scoring, or roadmap
    selection.

    Primary-domain authority therefore requires at least:

        SUPPORTED_AMBIGUOUS
        or
        EVIDENCE_RESOLVED
    """
    return [
        span
        for span in selected
        if (
            span.clause_role
            in _DOMAIN_ROLE_PRIORITY
            and _canonical_focus(span)
            is not None
            and span.resolution_status
            in {
                ResolutionStatus.EVIDENCE_RESOLVED,
                ResolutionStatus.SUPPORTED_AMBIGUOUS,
            }
        )
    ]


def _choose_primary_domain(
    selected: Sequence[ResolvedConceptSpan],
) -> Tuple[
    Optional[str],
    Optional[str],
    bool,
]:
    candidates = _domain_candidates(
        selected
    )

    if not candidates:
        return None, None, False

    # Only the strongest structural role represented in the query
    # may determine the primary domain.
    #
    # GOAL therefore beats SKILL_TARGET and ROLE.
    strongest_role_priority = max(
        _DOMAIN_ROLE_PRIORITY[
            span.clause_role
        ]
        for span in candidates
    )

    authoritative = [
        span
        for span in candidates
        if (
            _DOMAIN_ROLE_PRIORITY[
                span.clause_role
            ]
            == strongest_role_priority
        )
    ]

    # -----------------------------------------------------
    # QUERY-LEVEL DOMAIN CONFLICT POLICY
    #
    # The semantic unit here is the candidate segment, not only
    # textual overlap.
    #
    # Example:
    #
    #     want a data scientist dashboard for my job
    #
    # ``data`` and ``dashboard`` do not overlap, but both belong
    # to the same GOAL segment. If they independently resolve to
    # different focuses and no authoritative phrase establishes
    # one combined interpretation, confidence alone must not pick
    # a winner.
    #
    # This is intentionally conservative. A false abstention is
    # preferable to silently routing retrieval and planning into
    # the wrong domain.
    # -----------------------------------------------------

    by_segment: Dict[
        Optional[int],
        List[ResolvedConceptSpan],
    ] = {}

    for span in authoritative:
        by_segment.setdefault(
            span.segment_index,
            [],
        ).append(span)

    for segment_spans in (
        by_segment.values()
    ):
        reliable = [
            span
            for span in segment_spans
            if (
                span.resolution_status
                in {
                    ResolutionStatus.EVIDENCE_RESOLVED,
                    ResolutionStatus.SUPPORTED_AMBIGUOUS,
                }
                and _canonical_focus(span)
                is not None
            )
        ]

        focuses = {
            _canonical_focus(span)
            for span in reliable
        }

        focuses.discard(None)

        if len(focuses) <= 1:
            continue

        # A well-supported multi-token phrase is allowed to
        # disambiguate its own contained atomic readings.
        #
        # Example:
        #
        #     data engineering
        #
        # may resolve more reliably than its isolated ``data`` or
        # ``engineering`` constituents.
        disambiguating_phrases = [
            span
            for span in reliable
            if (
                span.ngram_size > 1
                and span.resolution_status
                == ResolutionStatus.EVIDENCE_RESOLVED
            )
        ]

        conflict_resolved = False

        for phrase in disambiguating_phrases:
            contained = [
                span
                for span in reliable
                if (
                    span is phrase
                    or _contains(
                        phrase,
                        span,
                    )
                )
            ]

            contained_focuses = {
                _canonical_focus(span)
                for span in contained
            }

            contained_focuses.discard(
                None
            )

            if (
                len(contained) >= 2
                and len(contained_focuses) >= 2
            ):
                conflict_resolved = True
                break

        if not conflict_resolved:
            return None, None, True

    ranked = sorted(
        authoritative,
        key=lambda span: (
            _STATUS_PRIORITY[
                span.resolution_status
            ],
            span.ngram_size,
            span.confidence,
            span.domain_margin,
            span.lexical_support_count,
        ),
        reverse=True,
    )

    winner = ranked[0]
    focus = _canonical_focus(winner)

    if focus is None:
        return None, None, False

    # IMPORTANT:
    #
    # Resolver evidence may contain historical or source-specific
    # family labels. The taxonomy module is the only authority for
    # focus -> family.
    family = get_domain_family(
        focus
    )

    if family == "general":
        family = None

    return focus, family, False


def semantic_priority_key(
    span: ResolvedConceptSpan,
):
    """
    Return the canonical semantic-importance ordering key.

    This module owns semantic ranking policy. Downstream projection and
    planning layers may consume this ordering but must not redefine it.

    The returned key may use resolver evidence internally; consumers do
    not need access to those resolver details.
    """
    return (
        _ANCHOR_ROLE_PRIORITY[
            span.clause_role
        ],
        _STATUS_PRIORITY[
            span.resolution_status
        ],
        span.ngram_size,
        span.confidence,
    )


def _anchor_key(
    span: ResolvedConceptSpan,
):
    return semantic_priority_key(
        span
    )


def _is_synthetic_unknown_composite(
    span: ResolvedConceptSpan,
) -> bool:
    """
    Return whether a multi-token span is only an unresolved
    composition of otherwise independent concepts.

    Example:

        python react ai

    The generated trigram is useful as structural provenance, but
    it is not a better user-facing anchor than the three concepts
    themselves.

    This rule is deliberately role/evidence based. It contains no
    technology vocabulary.
    """
    return (
        span.ngram_size > 1
        and span.clause_role
        == ClauseRole.UNKNOWN
        and span.resolution_status
        == ResolutionStatus.UNRESOLVED
    )


def _anchor_span_dominates(
    outer: ResolvedConceptSpan,
    inner: ResolvedConceptSpan,
) -> bool:
    """
    Decide whether ``outer`` is the semantically complete anchor
    representation of ``inner``.

    Compression is occurrence-local and role-local:

      * both spans must belong to the same semantic segment;
      * ``outer`` must strictly contain ``inner``;
      * both spans must express the same grammatical role.

    An unresolved ROLE phrase is still allowed to dominate its
    constituents because the occupational construction itself is
    strong structural evidence:

        cybersecurity analyst
        ML engineer

    Other phrases must have evidence at least as authoritative as
    the contained span. This prevents a weak or fabricated phrase
    from hiding a stronger atomic concept.

    Unresolved UNKNOWN composites never dominate.
    """
    if outer is inner:
        return False

    if (
        outer.segment_index is None
        or inner.segment_index is None
        or outer.segment_index
        != inner.segment_index
    ):
        return False

    if not _contains(
        outer,
        inner,
    ):
        return False

    if (
        outer.char_span
        == inner.char_span
    ):
        return False

    if (
        outer.clause_role
        != inner.clause_role
    ):
        return False

    if (
        outer.ngram_size
        <= inner.ngram_size
    ):
        return False

    if _is_synthetic_unknown_composite(
        outer
    ):
        return False

    # Closed occupational structure is independently meaningful,
    # even when corpus evidence does not contain the full phrase.
    if (
        outer.clause_role
        == ClauseRole.ROLE
    ):
        return True

    return (
        _STATUS_PRIORITY[
            outer.resolution_status
        ]
        >=
        _STATUS_PRIORITY[
            inner.resolution_status
        ]
        and outer.resolution_status
        != ResolutionStatus.UNRESOLVED
    )


def _compress_anchor_spans(
    selected: Sequence[ResolvedConceptSpan],
) -> List[ResolvedConceptSpan]:
    """
    Reduce overlap only for anchor presentation.

    ``selected_spans`` remains untouched and keeps complete
    occurrence-level provenance for later planning/reasoning.

    This layer removes redundant presentation anchors without
    collapsing genuinely distinct concepts, roles, segments, or
    open-world technologies.
    """
    usable = [
        span
        for span in selected
        if not _is_synthetic_unknown_composite(
            span
        )
    ]

    result = []

    for candidate in usable:
        dominated = any(
            _anchor_span_dominates(
                other,
                candidate,
            )
            for other in usable
            if other is not candidate
        )

        if dominated:
            continue

        result.append(candidate)

    return result


def _semantic_anchors(
    selected: Sequence[ResolvedConceptSpan],
    *,
    limit: int = 6,
) -> List[str]:
    """
    Produce compact semantic anchors for downstream planning.

    Anchor compression is structural rather than vocabulary based:

      * complete same-role phrases may subsume redundant
        constituents;
      * distinct roles and segments remain independent;
      * unresolved UNKNOWN composites do not replace atomic
        concepts;
      * unresolved/open-world technologies remain valid anchors.

    Examples:

        cybersecurity analyst portfolio using FastAPI
            -> cybersecurity analyst, FastAPI

        I want an AI project for an ML engineer role
            -> AI, ML engineer

        python react ai
            -> python / react / ai independently

        build something with ZorvexQL
            -> ZorvexQL
    """
    compressed = _compress_anchor_spans(
        selected
    )

    ranked = sorted(
        compressed,
        key=_anchor_key,
        reverse=True,
    )

    anchors = []
    seen = set()

    for span in ranked:
        normalized = (
            span.normalized_form or ""
        ).strip()

        surface = (
            span.surface_form or ""
        ).strip()

        if not normalized or not surface:
            continue

        # Presentation-level deduplication is intentionally
        # normalized-form based. Occurrence-level distinctions remain
        # preserved in selected_spans.
        if normalized in seen:
            continue

        seen.add(normalized)
        anchors.append(surface)

        if len(anchors) >= limit:
            break

    return anchors


def build_query_semantic_snapshot(
    query: str,
    *,
    max_n: int = 4,
    top_k: int = 6,
) -> QuerySemanticSnapshot:
    resolved = resolve_query_spans_shadow(
        query,
        max_n=max_n,
        top_k=top_k,
    )

    selected = _select_semantic_spans(
        resolved
    )

    (
        primary_focus,
        primary_family,
        domain_ambiguous,
    ) = _choose_primary_domain(
        selected
    )

    anchors = _semantic_anchors(
        selected
    )

    return QuerySemanticSnapshot(
        raw_query=query,
        resolved_spans=tuple(
            resolved
        ),
        selected_spans=tuple(
            selected
        ),
        primary_focus=primary_focus,
        primary_family=primary_family,
        anchors=tuple(
            anchors
        ),
        domain_ambiguous=(
            domain_ambiguous
        ),
    )
