from query_concept_resolution import ResolutionStatus
from query_concept_understanding import ClauseRole
from query_semantic_projections import (
    PlanningConcept,
    available_skills,
    build_planning_semantic_projection,
    learning_targets,
    mission_focus_concepts,
    required_stack,
)
from query_semantics import build_query_semantic_snapshot


def _triples(concepts):
    return [
        (
            concept.surface_form,
            concept.clause_role,
            concept.resolution_status.value,
        )
        for concept in concepts
    ]


def _planning_concept(
    surface: str,
    role: ClauseRole,
    start: int = 0,
) -> PlanningConcept:
    return PlanningConcept(
        surface_form=surface,
        normalized_form=surface.lower(),
        clause_role=role,
        resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
        char_span=(start, start + len(surface)),
        segment_index=0,
    )


def test_mission_focus_does_not_promote_held_skill():
    react = _planning_concept(
        "React",
        ClauseRole.SKILL_HELD,
    )

    assert mission_focus_concepts((react,)) == ()


def test_mission_focus_suppresses_unknown_when_intentional_concept_exists():
    goal = _planning_concept(
        "AI",
        ClauseRole.GOAL,
    )
    unknown = _planning_concept(
        "ZorvexQL",
        ClauseRole.UNKNOWN,
        3,
    )

    assert mission_focus_concepts(
        (goal, unknown)
    ) == (goal,)


def test_mission_focus_preserves_unknown_as_open_world_fallback():
    unknown = _planning_concept(
        "ZorvexQL",
        ClauseRole.UNKNOWN,
    )

    assert mission_focus_concepts(
        (unknown,)
    ) == (unknown,)


def test_projection_preserves_roles_instead_of_flattening_to_strings():
    snapshot = build_query_semantic_snapshot(
        "I know React but want an AI project using FastAPI"
    )

    projection = build_planning_semantic_projection(snapshot)

    ranked = [
        (concept.surface_form, concept.clause_role)
        for concept in projection.semantic_rank
    ]

    assert ("AI", ClauseRole.GOAL) in ranked
    assert ("FastAPI", ClauseRole.STACK_PREFERENCE) in ranked
    assert ("React", ClauseRole.SKILL_HELD) in ranked

    assert [
        concept.surface_form
        for concept in required_stack(projection)
    ] == ["FastAPI"]

    assert [
        concept.surface_form
        for concept in available_skills(projection)
    ] == ["React"]


def test_same_surface_concept_preserves_held_vs_learning_target_distinction():
    held_snapshot = build_query_semantic_snapshot(
        "I know Kubernetes"
    )
    target_snapshot = build_query_semantic_snapshot(
        "I want to learn Kubernetes"
    )

    held_projection = build_planning_semantic_projection(
        held_snapshot
    )
    target_projection = build_planning_semantic_projection(
        target_snapshot
    )

    assert [
        concept.surface_form
        for concept in available_skills(held_projection)
    ] == ["Kubernetes"]

    assert learning_targets(held_projection) == ()

    assert [
        concept.surface_form
        for concept in learning_targets(target_projection)
    ] == ["Kubernetes"]

    assert available_skills(target_projection) == ()


def test_open_world_unresolved_stack_survives_projection():
    snapshot = build_query_semantic_snapshot(
        "build something with ZorvexQL"
    )

    projection = build_planning_semantic_projection(snapshot)

    stack = required_stack(projection)

    assert len(stack) == 1
    assert stack[0].surface_form == "ZorvexQL"
    assert stack[0].normalized_form == "zorvexql"
    assert stack[0].clause_role == ClauseRole.STACK_PREFERENCE
    assert stack[0].resolution_status.value == "unresolved"


def test_semantic_rank_and_source_order_are_explicitly_separate():
    snapshot = build_query_semantic_snapshot(
        "AR VR education project"
    )

    projection = build_planning_semantic_projection(snapshot)

    semantic_surfaces = [
        concept.surface_form
        for concept in projection.semantic_rank
    ]

    source_surfaces = [
        concept.surface_form
        for concept in projection.source_order
    ]

    assert source_surfaces.index("AR") < source_surfaces.index("VR")
    assert source_surfaces.index("VR") < source_surfaces.index("education")

    assert semantic_surfaces != source_surfaces


def test_unknown_atomic_concepts_survive_without_synthetic_composite_requirement():
    snapshot = build_query_semantic_snapshot(
        "python react ai"
    )

    projection = build_planning_semantic_projection(snapshot)

    surfaces = {
        concept.surface_form.lower()
        for concept in projection.semantic_rank
    }

    assert {"python", "react", "ai"}.issubset(surfaces)


def test_empty_or_generic_query_does_not_create_projection_meaning():
    snapshot = build_query_semantic_snapshot(
        "something impressive"
    )

    projection = build_planning_semantic_projection(snapshot)

    assert all(
        concept.clause_role in {
            ClauseRole.UNKNOWN,
            ClauseRole.CONSTRAINT,
        }
        for concept in projection.semantic_rank
    )


def test_repeated_concepts_keep_occurrence_identity():
    snapshot = build_query_semantic_snapshot(
        "React Native app with React"
    )

    projection = build_planning_semantic_projection(snapshot)

    react_occurrences = [
        concept
        for concept in projection.source_order
        if "react" in concept.normalized_form
    ]

    assert len(react_occurrences) >= 2

    spans = [
        concept.char_span
        for concept in react_occurrences
    ]

    assert len(set(spans)) == len(spans)


def test_open_world_stack_query_does_not_require_known_stack_dictionary():
    snapshot = build_query_semantic_snapshot(
        "Build with Next.js and Tailwind"
    )

    projection = build_planning_semantic_projection(snapshot)

    surfaces = {
        concept.surface_form.lower()
        for concept in projection.semantic_rank
    }

    assert any("next" in surface for surface in surfaces)
    assert "tailwind" in surfaces


def test_projection_is_deterministic_and_pure():
    snapshot = build_query_semantic_snapshot(
        "I want a RAG app using Qdrant and want to learn Kubernetes"
    )

    before = tuple(snapshot.selected_spans)

    projection_one = build_planning_semantic_projection(snapshot)
    projection_two = build_planning_semantic_projection(snapshot)

    after = tuple(snapshot.selected_spans)

    assert projection_one == projection_two
    assert before == after
    assert snapshot.selected_spans == before


def test_projection_keeps_required_learning_and_available_buckets_distinct():
    snapshot = build_query_semantic_snapshot(
        "I know React, want to learn Kubernetes, and want to use FastAPI"
    )

    projection = build_planning_semantic_projection(snapshot)

    assert [
        concept.surface_form
        for concept in available_skills(projection)
    ] == ["React"]

    assert [
        concept.surface_form
        for concept in learning_targets(projection)
    ] == ["Kubernetes"]

    assert [
        concept.surface_form
        for concept in required_stack(projection)
    ] == ["FastAPI"]



def test_presentation_order_uses_canonical_compression_in_source_order():
    snapshot = build_query_semantic_snapshot(
        "AR VR education project"
    )

    projection = build_planning_semantic_projection(
        snapshot
    )

    assert [
        concept.surface_form
        for concept in projection.presentation_order
    ] == [
        "AR",
        "VR",
        "education",
    ]

    # Snapshot anchors retain canonical semantic-importance order.
    assert list(snapshot.anchors) == [
        "education",
        "AR",
        "VR",
    ]


def test_presentation_order_preserves_complete_role_phrase():
    snapshot = build_query_semantic_snapshot(
        "cybersecurity analyst portfolio using FastAPI"
    )

    projection = build_planning_semantic_projection(
        snapshot
    )

    assert [
        concept.surface_form
        for concept in projection.presentation_order
    ] == [
        "cybersecurity analyst",
        "FastAPI",
    ]

    assert (
        projection.presentation_order[0].clause_role
        == ClauseRole.ROLE
    )


def test_presentation_order_keeps_role_information_for_adapter_policy():
    snapshot = build_query_semantic_snapshot(
        "I know React but want an AI project using FastAPI"
    )

    projection = build_planning_semantic_projection(
        snapshot
    )

    presented = [
        (
            concept.surface_form,
            concept.clause_role,
        )
        for concept in projection.presentation_order
    ]

    assert ("React", ClauseRole.SKILL_HELD) in presented
    assert ("AI", ClauseRole.GOAL) in presented
    assert (
        "FastAPI",
        ClauseRole.STACK_PREFERENCE,
    ) in presented
