from planning.roadmap_execution_enrichment import (
    _anchor_phrase,
    enrich_roadmap_for_execution,
)
from query_concept_resolution import ResolutionStatus
from query_concept_understanding import ClauseRole
from query_semantic_projections import (
    PlanningConcept,
    PlanningSemanticProjection,
)
from schemas.product_models import RoadmapStage



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


def test_enrich_roadmap_adds_execution_fields():
    stages = [
        RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Turn the idea into a measurable problem.",
            tasks=["Write the problem statement."],
        ),
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement the smallest complete version.",
            tasks=["Create the first workflow."],
        ),
    ]

    enriched = enrich_roadmap_for_execution(
        stages=stages,
        idea={
            "project_title": "AR VR Education Learning Explorer",
            "suggested_tech_stack": ["Python", "FastAPI", "React"],
        },
    )

    assert enriched[0].stage_type == "mission_setup"
    assert enriched[0].objective
    assert enriched[0].why_it_matters
    assert enriched[0].commands
    assert enriched[0].expected_outputs
    assert enriched[0].acceptance_criteria
    assert enriched[0].validation_checks
    assert enriched[0].common_errors
    assert enriched[0].portfolio_artifact
    assert enriched[0].unlock_condition

    assert enriched[1].stage_type == "mission_build"
    assert any(
        "input-to-output" in criterion
        for criterion in enriched[1].acceptance_criteria
    )

def test_enrich_roadmap_uses_domain_playbook_context():
    from planning.mission_context import build_mission_context

    idea = {
        "project_title": "AR VR Education Learning Explorer",
        "project_summary": "Build an immersive classroom prototype.",
        "detected_domain": "education_tech",
        "suggested_tech_stack": ["Python", "FastAPI", "React"],
        "mvp_scope": ["Create one AR VR learning flow."],
        "advanced_extensions": ["Add student feedback tracking."],
    }

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
        idea=idea,
        user_goal="AR VR education project",
        planning_semantics=planning_semantics,
        resolved_planning_domain="education_tech",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["React", "Python"],
            "target_roles": ["Software Engineer"],
        },
        evidence_coverage={"coverage_state": "adequate_direct"},
    )

    stages = [
        RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Turn the idea into a measurable problem.",
            tasks=["Write the problem statement."],
        ),
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement the smallest complete version.",
            tasks=["Create the first workflow."],
        ),
        RoadmapStage(
            id="validate",
            title="Validate the result",
            purpose="Prove the system works.",
            tasks=["Run validation."],
        ),
    ]

    enriched = enrich_roadmap_for_execution(
        stages=stages,
        idea=idea,
        context=context,
    )

    combined = " ".join(
        [
            enriched[0].objective or "",
            " ".join(enriched[0].commands),
            " ".join(enriched[0].expected_outputs),
            " ".join(enriched[1].commands),
            " ".join(enriched[1].expected_outputs),
            " ".join(enriched[2].validation_checks),
        ]
    ).lower()

    assert "ar vr education" in combined
    assert "learning objective" in combined
    assert "student progress" in combined
    assert "data/learners.json" in combined
    assert "outputs/student_progress.json" in combined
    assert "react" in combined


def test_enriched_roadmap_attaches_guided_steps_when_context_is_available():
    from planning.mission_context import build_mission_context

    idea = {
        "project_title": "RAG Evaluation Studio",
        "project_summary": "Build a RAG evaluation workflow.",
        "detected_domain": "rag_llm",
        "suggested_tech_stack": ["Python", "FastAPI"],
        "mvp_scope": ["Create one retrieval evaluation workflow."],
        "advanced_extensions": ["Add reranking comparison."],
    }

    planning_semantics = _projection(
        _concept("RAG evaluation", ClauseRole.GOAL, 8),
        _concept("question answering", ClauseRole.GOAL, 35),
    )

    context = build_mission_context(
        idea=idea,
        user_goal="Build a RAG evaluation project for question answering",
        planning_semantics=planning_semantics,
        resolved_planning_domain="rag_llm",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["Python"],
            "target_roles": ["Machine Learning Engineer"],
        },
        evidence_coverage={"coverage_state": "strong_direct"},
    )

    stages = [
        RoadmapStage(
            id="define",
            title="Define the problem",
            purpose="Turn the idea into a measurable problem.",
        ),
        RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Implement the smallest complete version.",
        ),
    ]

    enriched = enrich_roadmap_for_execution(
        stages=stages,
        idea=idea,
        context=context,
    )

    assert enriched[0].guided_steps
    assert enriched[1].guided_steps

    guided_text = " ".join(
        " ".join(
            [
                step.title,
                step.explanation,
                step.action,
                step.starter_command or "",
                " ".join(step.starter_files),
                step.done_when,
                step.proof_prompt,
                " ".join(step.expected_output_patterns),
                step.interview_takeaway,
            ]
        )
        for stage in enriched
        for step in stage.guided_steps
    ).lower()

    assert "data/documents" in guided_text
    assert "data/eval_questions.json" in guided_text
    assert "retrieval" in guided_text
    assert "proof" in guided_text or "paste" in guided_text
    assert "interview" in guided_text or "structured the project" in guided_text

def test_empty_semantics_anchor_falls_back_to_project_title():
    from planning.mission_context import build_mission_context

    context = build_mission_context(
        idea={
            "project_title": "Fallback Project",
            "project_summary": "Build a useful project.",
            "suggested_tech_stack": [],
        },
        user_goal="something impressive",
        planning_semantics=_projection(),
        resolved_planning_domain="generic",
        constraints={},
        evidence_coverage={},
    )

    assert _anchor_phrase(context) == "Fallback Project"
