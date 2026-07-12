from planning.guided_step_generator import build_guided_steps_for_stage
from planning.mission_context import build_mission_context
from schemas.product_models import RoadmapStage


def _rag_context(skill_level="intermediate"):
    idea = {
        "project_title": "RAG Evaluation Studio",
        "project_summary": "Build a RAG evaluation workflow.",
        "detected_domain": "rag_llm",
        "suggested_tech_stack": ["Python", "FastAPI"],
        "mvp_scope": ["Create one retrieval evaluation workflow."],
        "advanced_extensions": ["Add reranking comparison."],
    }

    return build_mission_context(
        idea=idea,
        user_goal="Build a RAG evaluation project for question answering",
        query="Build a RAG evaluation project for question answering",
        resolved_planning_domain="rag_llm",
        constraints={
            "skill_level": skill_level,
            "time_available": "3 weeks",
            "preferred_stack": ["Python"],
            "target_roles": ["Machine Learning Engineer"],
        },
        evidence_coverage={"coverage_state": "strong_direct"},
    )


def _frontend_context():
    idea = {
        "project_title": "React Frontend Portfolio",
        "project_summary": "Build a frontend portfolio workflow.",
        "detected_domain": "frontend",
        "suggested_tech_stack": ["React", "TypeScript"],
        "mvp_scope": ["Create one interactive frontend workflow."],
    }

    return build_mission_context(
        idea=idea,
        user_goal="Build a React frontend portfolio project",
        query="Build a React frontend portfolio project",
        resolved_planning_domain="frontend",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": [],
            "target_roles": ["Frontend Engineer"],
        },
        evidence_coverage={"coverage_state": "strong_direct"},
    )


def test_define_stage_guides_rag_project_structure():
    steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="define",
            title="Define the project",
            purpose="Define the measurable project scope.",
        ),
        context=_rag_context(),
    )

    combined = " ".join(
        [
            step.title
            + " "
            + step.explanation
            + " "
            + step.action
            + " "
            + " ".join(step.starter_files)
            + " "
            + step.proof_prompt
            + " "
            + " ".join(step.expected_output_patterns)
            + " "
            + step.interview_takeaway
            for step in steps
        ]
    ).lower()

    assert len(steps) == 2
    assert "data/documents/" in combined
    assert "data/eval_questions.json" in combined
    assert "docs/problem_statement.md" in combined
    assert "retrieval_precision_at_3" in combined
    assert all(step.done_when for step in steps)
    assert all(step.proof_prompt for step in steps)
    assert all(step.interview_takeaway for step in steps)


def test_mvp_stage_guides_frontend_workflow():
    steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Build the smallest working version.",
        ),
        context=_frontend_context(),
    )

    combined = " ".join(
        [
            step.title
            + " "
            + (step.starter_command or "")
            + " "
            + " ".join(step.expected_output_patterns)
            + " "
            + step.proof_prompt
            for step in steps
        ]
    ).lower()

    assert len(steps) == 2
    assert "npm run dev" in combined
    assert "loading" in combined
    assert "error" in combined
    assert "success" in combined
    assert "outputs/sample_result.json" in combined


def test_beginner_guided_steps_omit_decision_points():
    steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="mvp",
            title="Build the MVP",
            purpose="Build the smallest working version.",
        ),
        context=_rag_context(skill_level="beginner"),
    )

    assert steps
    assert all(step.decision_point is None for step in steps)


def test_intermediate_guided_steps_include_decision_points():
    steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="validate",
            title="Validate the result",
            purpose="Validate the system.",
        ),
        context=_rag_context(skill_level="intermediate"),
    )

    assert steps
    assert any(step.decision_point for step in steps)


def test_guided_steps_avoid_duplicate_generic_folder_patterns():
    steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="define",
            title="Define the project",
            purpose="Define the measurable project scope.",
        ),
        context=_rag_context(),
    )

    structure_step = steps[0]

    assert structure_step.expected_output_patterns == [
        "data/documents/",
        "data/eval_questions.json",
        "src/ingest.py",
        "src/retriever.py",
    ]
    assert structure_step.expected_output_patterns.count("data") == 0
    assert structure_step.expected_output_patterns.count("src") == 0


def test_explanation_steps_require_reasoning_specific_patterns():
    validate_steps = build_guided_steps_for_stage(
        stage=RoadmapStage(
            id="validate",
            title="Validate the result",
            purpose="Validate the system.",
        ),
        context=_rag_context(),
    )

    failure_step = validate_steps[1]

    assert failure_step.expected_output_patterns == ["failure", "why", "improve"]
