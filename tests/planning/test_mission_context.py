from planning.mission_context import build_mission_context
from query_concept_resolution import ResolutionStatus
from query_concept_understanding import ClauseRole
from query_semantic_projections import (
    PlanningConcept,
    PlanningSemanticProjection,
)



def _concept(
    surface: str,
    role: ClauseRole,
    start: int,
    *,
    status: ResolutionStatus = ResolutionStatus.EVIDENCE_RESOLVED,
) -> PlanningConcept:
    return PlanningConcept(
        surface_form=surface,
        normalized_form=surface.lower(),
        clause_role=role,
        resolution_status=status,
        char_span=(start, start + len(surface)),
        segment_index=0,
    )


def _projection(
    *concepts: PlanningConcept,
) -> PlanningSemanticProjection:
    return PlanningSemanticProjection(
        semantic_rank=concepts,
        source_order=concepts,
        presentation_order=concepts,
    )


def test_build_mission_context_preserves_dynamic_project_signals():
    planning_semantics = _projection(
        _concept(
            "AR",
            ClauseRole.UNKNOWN,
            0,
            status=ResolutionStatus.UNRESOLVED,
        ),
        _concept(
            "VR",
            ClauseRole.UNKNOWN,
            3,
            status=ResolutionStatus.UNRESOLVED,
        ),
        _concept(
            "education",
            ClauseRole.UNKNOWN,
            6,
            status=ResolutionStatus.UNRESOLVED,
        ),
    )

    context = build_mission_context(
        idea={
            "project_title": "AR VR Education Learning Explorer",
            "project_summary": "Build an immersive classroom prototype.",
            "detected_domain": "education_tech",
            "suggested_tech_stack": ["Python", "FastAPI", "React"],
            "mvp_scope": ["Create one AR VR learning flow."],
            "advanced_extensions": ["Add student feedback tracking."],
        },
        user_goal="AR VR education project",
        planning_semantics=planning_semantics,
        resolved_planning_domain="education_tech",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["React", "Python"],
            "target_roles": ["Software Engineer"],
        },
        evidence_coverage={
            "coverage_state": "adequate_direct",
            "warnings": ["limited_direct_evidence"],
        },
    )

    assert context.project_title == "AR VR Education Learning Explorer"
    assert context.resolved_planning_domain == "education_tech"
    assert [
        concept.surface_form
        for concept in context.planning_concepts[:3]
    ] == ["AR", "VR", "education"]
    assert context.skill_level == "intermediate"
    assert context.timeline_bucket == "2_3_weeks"
    assert context.primary_stack[:3] == ["React", "Python", "FastAPI"]
    assert context.target_roles == ["Software Engineer"]
    assert context.evidence_coverage_state == "adequate_direct"
    assert context.mvp_steps == ["Create one AR VR learning flow."]
    assert context.warnings == ["limited_direct_evidence"]


def test_mission_context_falls_back_to_generic_playbook():
    context = build_mission_context(
        idea={
            "project_title": "Unknown Domain Build",
            "project_summary": "Build something unusual.",
            "detected_domain": "unknown_domain",
        },
        user_goal="unusual project",
        planning_semantics=_projection(),
        resolved_planning_domain="unknown_domain",
        constraints={},
        evidence_coverage={},
    )

    assert context.playbook.domain == "generic"


def test_timeline_bucket_handles_one_week():
    context = build_mission_context(
        idea={
            "project_title": "Fast Build",
            "project_summary": "Build quickly.",
            "detected_domain": "generic",
        },
        user_goal="fast project",
        planning_semantics=_projection(),
        resolved_planning_domain="generic",
        constraints={"time_available": "1 week"},
        evidence_coverage={},
    )

    assert context.timeline_bucket == "1_week"


def test_mission_context_prefers_semantic_requested_stack_before_idea_stack():
    planning_semantics = _projection(
        _concept("React", ClauseRole.STACK_PREFERENCE, 8),
        _concept("frontend portfolio", ClauseRole.GOAL, 14),
    )

    context = build_mission_context(
        idea={
            "project_title": "React Frontend Portfolio Frontend Experience",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        },
        user_goal="Build a React frontend portfolio project",
        planning_semantics=planning_semantics,
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.requested_stack == ["React"]
    assert context.primary_stack == [
        "React",
        "Python",
        "FastAPI",
        "PostgreSQL",
    ]


def test_mission_context_consumes_typed_stack_preferences():
    planning_semantics = _projection(
        _concept("Next.js", ClauseRole.STACK_PREFERENCE, 8),
        _concept("TypeScript", ClauseRole.STACK_PREFERENCE, 28),
        _concept("frontend", ClauseRole.GOAL, 16),
    )

    context = build_mission_context(
        idea={
            "project_title": "Next Frontend Build",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python"],
        },
        user_goal="Build a Next.js frontend in TypeScript",
        planning_semantics=planning_semantics,
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.requested_stack == ["Next.js", "TypeScript"]
    assert context.primary_stack == [
        "Next.js",
        "TypeScript",
        "Python",
    ]


def test_mission_context_keeps_idea_stack_when_query_has_no_stack_terms():
    context = build_mission_context(
        idea={
            "project_title": "Frontend Portfolio Experience",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        },
        user_goal="Build a portfolio project",
        planning_semantics=_projection(),
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.primary_stack[:3] == ["Python", "FastAPI", "PostgreSQL"]

def test_requested_stack_preserves_user_precedence_and_first_wins_dedupe():
    planning_semantics = _projection(
        _concept("fastapi", ClauseRole.STACK_PREFERENCE, 0),
        _concept("Qdrant", ClauseRole.STACK_PREFERENCE, 8),
    )

    context = build_mission_context(
        idea={
            "project_title": "AI Retrieval Build",
            "project_summary": "Build a retrieval workflow.",
            "suggested_tech_stack": [
                "React",
                "Python",
                "PostgreSQL",
            ],
        },
        user_goal="Build a retrieval workflow",
        planning_semantics=planning_semantics,
        resolved_planning_domain="rag_llm",
        constraints={
            "preferred_stack": [
                "Python",
                "FastAPI",
            ],
        },
        evidence_coverage={},
    )

    assert context.requested_stack == [
        "Python",
        "FastAPI",
        "Qdrant",
    ]
    assert context.primary_stack == [
        "Python",
        "FastAPI",
        "Qdrant",
        "React",
        "PostgreSQL",
    ]


def test_primary_stack_does_not_truncate_requested_technologies():
    requested = [
        "Next.js",
        "Tailwind",
        "PostgreSQL",
        "Redis",
        "Docker",
        "Kubernetes",
        "FastAPI",
    ]

    context = build_mission_context(
        idea={
            "project_title": "Platform Build",
            "project_summary": "Build a platform.",
            "suggested_tech_stack": [
                "Python",
                "React",
            ],
        },
        user_goal="Build a platform",
        planning_semantics=_projection(),
        resolved_planning_domain="generic",
        constraints={
            "preferred_stack": requested,
        },
        evidence_coverage={},
    )

    assert context.requested_stack == requested
    assert context.primary_stack == requested + [
        "Python",
        "React",
    ]


def test_already_injected_preferred_stack_is_not_reordered_or_duplicated():
    context = build_mission_context(
        idea={
            "project_title": "Frontend Build",
            "project_summary": "Build a frontend.",
            "suggested_tech_stack": [
                "Python",
                "React",
                "FastAPI",
            ],
        },
        user_goal="Build a frontend",
        planning_semantics=_projection(),
        resolved_planning_domain="frontend",
        constraints={
            "preferred_stack": [
                "React",
                "Python",
            ],
        },
        evidence_coverage={},
    )

    assert context.requested_stack == [
        "React",
        "Python",
    ]
    assert context.primary_stack == [
        "React",
        "Python",
        "FastAPI",
    ]


def test_learning_targets_and_held_skills_stay_out_of_primary_stack():
    planning_semantics = _projection(
        _concept("React", ClauseRole.SKILL_HELD, 0),
        _concept("Kubernetes", ClauseRole.SKILL_TARGET, 10),
        _concept("FastAPI", ClauseRole.STACK_PREFERENCE, 25),
    )

    context = build_mission_context(
        idea={
            "project_title": "AI Service",
            "project_summary": "Build an AI service.",
            "suggested_tech_stack": ["Python"],
        },
        user_goal=(
            "I know React and want to learn Kubernetes "
            "while using FastAPI"
        ),
        planning_semantics=planning_semantics,
        resolved_planning_domain="ai_ml",
        constraints={},
        evidence_coverage={},
    )

    assert context.requested_stack == ["FastAPI"]
    assert context.learning_targets == ["Kubernetes"]
    assert context.available_skills == ["React"]
    assert context.primary_stack == [
        "FastAPI",
        "Python",
    ]
    assert "React" not in context.primary_stack
    assert "Kubernetes" not in context.primary_stack


def test_structured_and_semantic_target_roles_remain_separate():
    planning_semantics = _projection(
        _concept("ML engineer", ClauseRole.ROLE, 0),
    )

    context = build_mission_context(
        idea={
            "project_title": "ML Portfolio",
            "project_summary": "Build an ML portfolio project.",
            "suggested_tech_stack": ["Python"],
        },
        user_goal="Build something for an ML engineer role",
        planning_semantics=planning_semantics,
        resolved_planning_domain="ai_ml",
        constraints={
            "target_roles": ["Software Engineer"],
        },
        evidence_coverage={},
    )

    assert context.target_roles == ["Software Engineer"]
    assert context.semantic_target_roles == ["ML engineer"]
