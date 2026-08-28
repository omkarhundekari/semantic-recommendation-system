from planning.mission_context import build_mission_context
from planning.mission_specificity_validator import (
    validate_mission_specificity,
    validate_roadmap_specificity,
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


def _context():
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

    return build_mission_context(
        idea={
            "project_title": "AR VR Education Learning Explorer",
            "project_summary": "Build an immersive classroom prototype.",
            "detected_domain": "education_tech",
            "suggested_tech_stack": ["Python", "FastAPI", "React"],
            "mvp_scope": ["Create one AR VR learning flow."],
        },
        user_goal="AR VR education project",
        planning_semantics=planning_semantics,
        resolved_planning_domain="education_tech",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["React", "Python"],
        },
        evidence_coverage={"coverage_state": "adequate_direct"},
    )


def test_validator_passes_specific_mission():
    context = _context()

    mission = RoadmapStage(
        id="mvp",
        title="Build the AR VR Education prototype",
        purpose="Implement the first AR VR education learning flow.",
        objective=(
            "Build a React and Python AR VR Education workflow that produces "
            "one measurable classroom learning output."
        ),
        commands=[
            "mkdir -p data docs src tests outputs",
            "touch data/learners.json docs/learning_objectives.md",
            "# React frontend and Python API workflow",
        ],
        expected_outputs=[
            "A React screen renders one AR VR classroom activity.",
            "The Python API returns one classroom activity payload.",
            "docs/learning_objectives.md contains the learning objective alignment.",
            "outputs/student_progress.json contains the student progress tracking result.",
        ],
        acceptance_criteria=[
            "The React page renders one AR VR classroom activity.",
            "The Python endpoint returns a saved classroom output.",
            "outputs/student_progress.json exists after the feedback loop runs.",
        ],
        validation_checks=[
            "Run the React page and confirm the activity loads.",
            "Call the Python endpoint and confirm it returns output JSON.",
        ],
        portfolio_artifact="README.md and outputs/sample_result.json",
        unlock_condition="Unlocks when the AR VR classroom flow runs end to end.",
    )

    report = validate_mission_specificity(mission=mission, context=context)

    assert report.passed
    assert report.violations == []


def test_validator_catches_missing_mission_focus():
    context = _context()

    mission = RoadmapStage(
        id="mvp",
        title="Build the prototype",
        purpose="Build a student learning prototype.",
        objective="Build a student learning workflow.",
        expected_outputs=["A result exists."],
        acceptance_criteria=["The output exists."],
        validation_checks=["Confirm the output exists."],
        commands=["python app.py"],
    )

    report = validate_mission_specificity(mission=mission, context=context)

    assert not report.passed
    assert any(
        "Objective missing mission focus concept" in item
        for item in report.violations
    )



def test_validator_does_not_require_held_skill_in_objective():
    planning_semantics = _projection(
        _concept("React", ClauseRole.SKILL_HELD, 0),
        _concept("AI", ClauseRole.GOAL, 10),
        _concept("FastAPI", ClauseRole.STACK_PREFERENCE, 20),
    )

    context = build_mission_context(
        idea={
            "project_title": "AI Workflow",
            "project_summary": "Build an AI workflow.",
            "suggested_tech_stack": ["Python", "FastAPI"],
            "mvp_scope": ["Build one AI workflow."],
        },
        user_goal="I know React but want an AI project using FastAPI",
        planning_semantics=planning_semantics,
        resolved_planning_domain="ai_ml",
        constraints={},
        evidence_coverage={"coverage_state": "adequate_direct"},
    )

    mission = RoadmapStage(
        id="mvp",
        title="Build the AI workflow",
        purpose="Build the first AI workflow.",
        objective="Build an AI workflow using FastAPI.",
        expected_outputs=["An AI workflow output exists."],
        acceptance_criteria=["The FastAPI workflow returns one output."],
        validation_checks=["Confirm the AI workflow returns output."],
        commands=["python app.py"],
    )

    report = validate_mission_specificity(
        mission=mission,
        context=context,
    )

    assert not any(
        "React" in violation
        and "mission focus" in violation
        for violation in report.violations
    )


def test_validator_catches_weak_acceptance_criteria():
    context = _context()

    mission = RoadmapStage(
        id="define",
        title="Define the AR VR Education scope",
        purpose="Define the AR VR Education project.",
        objective="Define the AR VR Education scope with React and Python.",
        expected_outputs=["A problem statement exists."],
        acceptance_criteria=["The project feels clear."],
        validation_checks=["Confirm the problem statement exists."],
        commands=["mkdir -p docs src"],
    )

    report = validate_mission_specificity(mission=mission, context=context)

    assert not report.passed
    assert any("Acceptance criteria" in item for item in report.violations)


def test_roadmap_validator_prefixes_stage_ids():
    context = _context()

    missions = [
        RoadmapStage(
            id="define",
            title="Define scope",
            purpose="Define scope.",
            objective="Define scope.",
        )
    ]

    report = validate_roadmap_specificity(missions=missions, context=context)

    assert not report.passed
    assert any(item.startswith("define:") for item in report.violations)

def test_validator_skips_focus_requirement_when_semantics_are_empty():
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

    mission = RoadmapStage(
        id="mvp",
        title="Build the project",
        purpose="Build the first working version.",
        objective="Build one working workflow.",
        expected_outputs=["A working output exists."],
        acceptance_criteria=["The workflow returns an output."],
        validation_checks=["Confirm the workflow returns output."],
        commands=["python app.py"],
    )

    report = validate_mission_specificity(
        mission=mission,
        context=context,
    )

    assert not any(
        "mission focus" in violation.lower()
        for violation in report.violations
    )
