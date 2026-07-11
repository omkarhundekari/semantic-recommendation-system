from __future__ import annotations

from typing import Any, List

from schemas.product_models import RoadmapStage


def enrich_roadmap_for_execution(
    *,
    stages: List[RoadmapStage],
    idea: dict[str, Any],
) -> List[RoadmapStage]:
    project_title = str(idea.get("project_title", "the project")).strip()
    tech_stack = list(idea.get("suggested_tech_stack", []) or [])
    primary_stack = ", ".join(str(item) for item in tech_stack[:3]) or "your chosen stack"

    enriched = []

    for stage in stages:
        enriched.append(
            stage.model_copy(
                update={
                    "stage_type": _stage_type(stage.id),
                    "objective": _objective(stage=stage, project_title=project_title),
                    "why_it_matters": _why_it_matters(stage.id),
                    "commands": _commands(stage.id, primary_stack),
                    "expected_outputs": _expected_outputs(stage.id, project_title),
                    "acceptance_criteria": _acceptance_criteria(stage=stage),
                    "validation_checks": _validation_checks(stage.id),
                    "common_errors": _common_errors(stage.id),
                    "portfolio_artifact": _portfolio_artifact(stage.id),
                    "unlock_condition": _unlock_condition(stage.id),
                }
            )
        )

    return enriched


def _stage_type(stage_id: str) -> str:
    mapping = {
        "define": "mission_setup",
        "mvp": "mission_build",
        "validate": "mission_validate",
        "extend": "mission_extend",
        "package": "mission_package",
    }
    return mapping.get(stage_id, "mission")


def _objective(*, stage: RoadmapStage, project_title: str) -> str:
    if stage.id == "define":
        return f"Turn {project_title} into a narrow, testable build target."
    if stage.id == "mvp":
        return f"Build the smallest working version of {project_title}."
    if stage.id == "validate":
        return "Prove the prototype works on representative inputs."
    if stage.id == "extend":
        return "Add one advanced feature only after the MVP is stable."
    if stage.id == "package":
        return "Turn the finished build into a portfolio-ready artifact."

    return stage.purpose


def _why_it_matters(stage_id: str) -> str:
    mapping = {
        "define": (
            "A clear definition prevents the project from becoming a vague demo "
            "with no measurable finish line."
        ),
        "mvp": (
            "The MVP creates the first complete loop from input to output, which "
            "is the foundation for every later improvement."
        ),
        "validate": (
            "Validation turns a working prototype into a credible engineering "
            "project by showing where it succeeds and fails."
        ),
        "extend": (
            "A focused extension adds technical depth without destabilizing the "
            "core build."
        ),
        "package": (
            "Packaging converts the build into something recruiters, professors, "
            "or teammates can understand quickly."
        ),
    }
    return mapping.get(
        stage_id,
        "This mission moves the project closer to a working portfolio build.",
    )


def _commands(stage_id: str, primary_stack: str) -> List[str]:
    if stage_id == "define":
        return [
            "mkdir -p docs data backend frontend",
            "touch README.md docs/problem_statement.md docs/validation_plan.md",
        ]

    if stage_id == "mvp":
        return [
            "# Create the first working input-to-output path using your selected stack",
            f"# Primary stack to consider: {primary_stack}",
        ]

    if stage_id == "validate":
        return [
            "mkdir -p tests outputs",
            "# Add representative inputs and save observed outputs",
        ]

    if stage_id == "extend":
        return [
            "# Pick one extension and implement it behind a small, testable interface",
        ]

    if stage_id == "package":
        return [
            "touch docs/demo_script.md docs/architecture_notes.md",
            "# Update README.md with setup, screenshots, and validation results",
        ]

    return []


def _expected_outputs(stage_id: str, project_title: str) -> List[str]:
    mapping = {
        "define": [
            "A one-sentence problem statement.",
            "A list of expected inputs and outputs.",
            "A measurable done condition.",
        ],
        "mvp": [
            f"A runnable first version of {project_title}.",
            "At least one example input that produces a meaningful output.",
        ],
        "validate": [
            "A small validation set or checklist.",
            "A written summary of what worked, failed, and needs improvement.",
        ],
        "extend": [
            "One advanced capability connected to the MVP.",
            "A before/after note explaining what improved.",
        ],
        "package": [
            "A clean README.",
            "A demo script.",
            "A portfolio-ready explanation of the architecture and tradeoffs.",
        ],
    }
    return mapping.get(stage_id, [])


def _acceptance_criteria(stage: RoadmapStage) -> List[str]:
    criteria = [
        "You can explain what this stage produced in two sentences.",
        "The output is saved in the repository, not just kept in your head.",
    ]

    if stage.tasks:
        criteria.append(
            "Each listed task has either been completed or intentionally deferred."
        )

    if stage.id == "mvp":
        criteria.append(
            "A user can run or inspect one complete input-to-output workflow."
        )

    if stage.id == "validate":
        criteria.append("At least one failure case or limitation is documented.")

    if stage.id == "package":
        criteria.append(
            "The project can be understood from the README without a live explanation."
        )

    return criteria


def _validation_checks(stage_id: str) -> List[str]:
    mapping = {
        "define": [
            "Check that the problem statement names a user, input, output, and success metric.",
        ],
        "mvp": [
            "Run the main script, API route, or UI flow from a clean terminal.",
            "Confirm the output changes when the input changes.",
        ],
        "validate": [
            "Run the same validation examples twice and compare results.",
            "Record at least one metric, observation, or qualitative judgment.",
        ],
        "extend": [
            "Verify the original MVP still works after the extension.",
        ],
        "package": [
            "Follow your own README setup instructions from the beginning.",
        ],
    }
    return mapping.get(stage_id, [])


def _common_errors(stage_id: str) -> List[str]:
    mapping = {
        "define": [
            "Choosing a topic that is too broad to finish.",
            "Skipping success metrics.",
        ],
        "mvp": [
            "Building separate pieces that never connect.",
            "Adding advanced features before the core workflow runs.",
        ],
        "validate": [
            "Only testing happy-path examples.",
            "Not saving outputs or observations.",
        ],
        "extend": [
            "Adding multiple extensions at once.",
            "Breaking the MVP while chasing complexity.",
        ],
        "package": [
            "Writing a README that describes the idea but not how to run it.",
            "Leaving out limitations and tradeoffs.",
        ],
    }
    return mapping.get(stage_id, [])


def _portfolio_artifact(stage_id: str) -> str:
    mapping = {
        "define": "docs/problem_statement.md",
        "mvp": "A runnable MVP commit with setup instructions.",
        "validate": "docs/validation_plan.md and saved outputs.",
        "extend": "A documented advanced feature with before/after notes.",
        "package": "README.md, demo script, architecture notes, and resume bullet.",
    }
    return mapping.get(stage_id, "A saved project artifact.")


def _unlock_condition(stage_id: str) -> str:
    mapping = {
        "define": "Unlocks when the project has a narrow problem, input, output, and success metric.",
        "mvp": "Unlocks when the first input-to-output workflow runs.",
        "validate": "Unlocks when validation examples and results are documented.",
        "extend": "Unlocks when one advanced feature is implemented without breaking the MVP.",
        "package": "Unlocks when the project is ready to show publicly.",
    }
    return mapping.get(stage_id, "Unlocks when the mission output is complete.")
