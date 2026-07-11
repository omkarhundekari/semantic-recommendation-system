from planning.mission_context import build_mission_context
from planning.mission_specificity_validator import (
    validate_mission_specificity,
    validate_roadmap_specificity,
)
from schemas.product_models import RoadmapStage


def _context():
    return build_mission_context(
        idea={
            "project_title": "AR VR Education Learning Explorer",
            "project_summary": "Build an immersive classroom prototype.",
            "detected_domain": "education_tech",
            "suggested_tech_stack": ["Python", "FastAPI", "React"],
            "mvp_scope": ["Create one AR VR learning flow."],
        },
        user_goal="AR VR education project",
        query="AR VR education project",
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
            "mkdir -p docs src tests outputs",
            "# React frontend and Python API workflow",
        ],
        expected_outputs=[
            "A React screen renders one AR VR classroom activity.",
            "The Python API returns one classroom activity payload.",
            "docs/problem_statement.md contains the scoped input-output workflow.",
        ],
        acceptance_criteria=[
            "The React page renders one AR VR classroom activity.",
            "The Python endpoint returns a saved classroom output.",
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


def test_validator_catches_missing_query_anchor():
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
    assert any("Objective missing query anchor" in item for item in report.violations)


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
