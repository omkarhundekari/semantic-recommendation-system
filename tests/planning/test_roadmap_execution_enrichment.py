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
