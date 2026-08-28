from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from query_concept_resolution import (
    ResolutionStatus,
    ResolvedConceptSpan,
)
from query_concept_understanding import ClauseRole
from query_semantics import (
    QuerySemanticSnapshot,
    semantic_anchor_spans,
    semantic_priority_key,
)


@dataclass(frozen=True)
class PlanningConcept:
    """
    Narrow planning-facing semantic concept.

    This deliberately excludes resolver internals such as evidence counts,
    domain margins, lexical scores, and corpus metadata.

    Planning receives only the semantic identity and occurrence provenance
    needed to preserve the user's intent without reparsing the raw query.
    """

    surface_form: str
    normalized_form: str
    clause_role: ClauseRole
    resolution_status: ResolutionStatus
    char_span: tuple[int, int] | None
    segment_index: int | None


@dataclass(frozen=True)
class PlanningSemanticProjection:
    """
    Pure planning projection over canonical query semantics.

    semantic_rank
        Complete selected concepts in canonical semantic-importance order.

    source_order
        Complete selected concepts in stable occurrence order from the
        user's original query.

    presentation_order
        Canonically compressed and deduplicated semantic-anchor concepts,
        arranged back into source order for natural presentation.

    Semantic importance, occurrence provenance, and presentation order are
    deliberately separate views over the same canonical authority.
    """

    semantic_rank: Tuple[PlanningConcept, ...]
    source_order: Tuple[PlanningConcept, ...]
    presentation_order: Tuple[PlanningConcept, ...]


def build_planning_semantic_projection(
    snapshot: QuerySemanticSnapshot,
) -> PlanningSemanticProjection:
    """
    Build a planning-safe view from the canonical semantic snapshot.

    This function MUST NOT:
      * reparse snapshot.raw_query;
      * perform new domain inference;
      * perform new role inference;
      * mutate snapshot.selected_spans;
      * introduce technology dictionaries or aliases.

    It only projects already-resolved canonical semantics.
    """

    ranked_spans = _planning_ranked_spans(
        snapshot.selected_spans
    )

    source_spans = sorted(
        snapshot.selected_spans,
        key=_source_order_key,
    )

    presentation_spans = sorted(
        semantic_anchor_spans(
            snapshot.selected_spans
        ),
        key=_source_order_key,
    )

    return PlanningSemanticProjection(
        semantic_rank=tuple(
            _to_planning_concept(span)
            for span in ranked_spans
        ),
        source_order=tuple(
            _to_planning_concept(span)
            for span in source_spans
        ),
        presentation_order=tuple(
            _to_planning_concept(span)
            for span in presentation_spans
        ),
    )


def concepts_for_role(
    projection: PlanningSemanticProjection,
    role: ClauseRole,
    *,
    source_order: bool = False,
) -> Tuple[PlanningConcept, ...]:
    """
    Return concepts for one canonical grammatical role.

    Role grouping remains a projection operation rather than duplicated
    state stored on QuerySemanticSnapshot.
    """

    concepts = (
        projection.source_order
        if source_order
        else projection.semantic_rank
    )

    return tuple(
        concept
        for concept in concepts
        if concept.clause_role == role
    )


def required_stack(
    projection: PlanningSemanticProjection,
) -> Tuple[PlanningConcept, ...]:
    return concepts_for_role(
        projection,
        ClauseRole.STACK_PREFERENCE,
    )


def learning_targets(
    projection: PlanningSemanticProjection,
) -> Tuple[PlanningConcept, ...]:
    return concepts_for_role(
        projection,
        ClauseRole.SKILL_TARGET,
    )


def available_skills(
    projection: PlanningSemanticProjection,
) -> Tuple[PlanningConcept, ...]:
    return concepts_for_role(
        projection,
        ClauseRole.SKILL_HELD,
    )


def target_roles(
    projection: PlanningSemanticProjection,
) -> Tuple[PlanningConcept, ...]:
    return concepts_for_role(
        projection,
        ClauseRole.ROLE,
    )


def goals(
    projection: PlanningSemanticProjection,
) -> Tuple[PlanningConcept, ...]:
    return concepts_for_role(
        projection,
        ClauseRole.GOAL,
    )



def mission_focus_concepts(
    concepts: Sequence[PlanningConcept],
) -> Tuple[PlanningConcept, ...]:
    intentional_roles = {
        ClauseRole.GOAL,
        ClauseRole.ROLE,
        ClauseRole.STACK_PREFERENCE,
    }

    intentional = tuple(
        concept
        for concept in concepts
        if concept.clause_role in intentional_roles
    )

    if intentional:
        return intentional

    return tuple(
        concept
        for concept in concepts
        if concept.clause_role == ClauseRole.UNKNOWN
    )


def _to_planning_concept(
    span: ResolvedConceptSpan,
) -> PlanningConcept:
    return PlanningConcept(
        surface_form=span.surface_form,
        normalized_form=span.normalized_form,
        clause_role=span.clause_role,
        resolution_status=span.resolution_status,
        char_span=span.char_span,
        segment_index=span.segment_index,
    )


def _planning_ranked_spans(
    spans: Sequence[ResolvedConceptSpan],
) -> list[ResolvedConceptSpan]:
    """
    Consume canonical semantic ordering without redefining it here.

    query_semantics remains the sole owner of semantic ranking policy.
    This projection only converts that ordering into a narrow
    planning-facing representation.
    """
    return sorted(
        spans,
        key=semantic_priority_key,
        reverse=True,
    )


def _source_order_key(
    span: ResolvedConceptSpan,
) -> tuple[int, int, int]:
    if span.char_span is None:
        return (
            10**9,
            10**9,
            span.segment_index
            if span.segment_index is not None
            else 10**9,
        )

    start, end = span.char_span

    return (
        start,
        end,
        span.segment_index
        if span.segment_index is not None
        else 10**9,
    )
