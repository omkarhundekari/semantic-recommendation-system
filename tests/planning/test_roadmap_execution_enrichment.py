from planning.roadmap_execution_enrichment import enrich_roadmap_for_execution
from schemas.product_models import RoadmapStage


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

    context = build_mission_context(
        idea=idea,
        user_goal="AR VR education project",
        query="AR VR education project",
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
