from schemas.product_models import GuidedMissionStep, RoadmapStage


def test_guided_mission_step_schema_supports_beginner_execution_guidance():
    step = GuidedMissionStep(
        step_id="create-project-structure",
        title="Create your project structure",
        explanation=(
            "Separate source documents, code, tests, and outputs before "
            "building the project."
        ),
        action="Create the starter folders for the project.",
        starter_command="mkdir -p data/documents outputs src tests",
        starter_files=["data/documents/", "outputs/", "src/", "tests/"],
        done_when="All four folders exist in the repository root.",
        common_confusion=(
            "Do not put generated answers inside data/documents; that folder "
            "is only for source material."
        ),
        proof_type="folder_confirm",
        proof_prompt="Paste the output of ls from your project root.",
        expected_output_patterns=["data", "outputs", "src", "tests"],
        interview_takeaway=(
            "I separated retrieval data, code, tests, and outputs from the "
            "start so evaluation stayed clean."
        ),
    )

    stage = RoadmapStage(
        id="define",
        title="Define the project",
        purpose="Turn the idea into a measurable build.",
        guided_steps=[step],
    )

    assert stage.guided_steps[0].step_id == "create-project-structure"
    assert stage.guided_steps[0].proof_type == "folder_confirm"
    assert "outputs" in stage.guided_steps[0].expected_output_patterns


def test_roadmap_stage_defaults_to_no_guided_steps():
    stage = RoadmapStage(
        id="mvp",
        title="Build the MVP",
        purpose="Build the smallest working version.",
    )

    assert stage.guided_steps == []
