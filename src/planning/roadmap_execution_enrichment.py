from __future__ import annotations

from typing import Any, List, Optional

from planning.guided_step_generator import build_guided_steps_for_stage
from planning.mission_context import MissionContext
from query_semantic_projections import mission_focus_concepts
from schemas.product_models import RoadmapStage


def enrich_roadmap_for_execution(
    *,
    stages: List[RoadmapStage],
    idea: dict[str, Any],
    context: Optional[MissionContext] = None,
) -> List[RoadmapStage]:
    project_title = str(idea.get("project_title", "the project")).strip()
    tech_stack = list(idea.get("suggested_tech_stack", []) or [])

    if context:
        primary_stack = ", ".join(context.primary_stack[:3]) or "your chosen stack"
    else:
        primary_stack = ", ".join(str(item) for item in tech_stack[:3]) or "your chosen stack"

    enriched = []

    for stage in stages:
        enriched.append(
            stage.model_copy(
                update={
                    "stage_type": _stage_type(stage.id),
                    "objective": _objective(
                        stage=stage,
                        project_title=project_title,
                        context=context,
                    ),
                    "why_it_matters": _why_it_matters(stage.id, context),
                    "commands": _commands(stage.id, primary_stack, context),
                    "expected_outputs": _expected_outputs(
                        stage.id,
                        project_title,
                        context,
                    ),
                    "acceptance_criteria": _acceptance_criteria(
                        stage=stage,
                        context=context,
                    ),
                    "validation_checks": _validation_checks(stage.id, context),
                    "common_errors": _common_errors(stage.id, context),
                    "portfolio_artifact": _portfolio_artifact(stage.id, context),
                    "unlock_condition": _unlock_condition(stage.id, context),
                    "guided_steps": (
                        build_guided_steps_for_stage(
                            stage=stage,
                            context=context,
                        )
                        if context
                        else stage.guided_steps
                    ),
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


def _objective(
    *,
    stage: RoadmapStage,
    project_title: str,
    context: Optional[MissionContext] = None,
) -> str:
    if context:
        anchor_phrase = _anchor_phrase(context)
        domain_focus = _domain_focus(context)

        if stage.id == "define":
            return (
                f"Define the {anchor_phrase} scope for {project_title} using "
                f"{domain_focus} as the core project lens."
            )
        if stage.id == "mvp":
            return (
                f"Build the smallest working {anchor_phrase} workflow for "
                f"{project_title} with {domain_focus} outputs."
            )
        if stage.id == "validate":
            return (
                f"Validate the {anchor_phrase} workflow using "
                f"{_metric_phrase(context)} and concrete test cases."
            )
        if stage.id == "extend":
            return (
                f"Add one advanced {anchor_phrase} capability without breaking "
                f"the validated MVP workflow."
            )
        if stage.id == "package":
            return (
                f"Package {project_title} as a portfolio-ready {anchor_phrase} "
                f"project with evidence, demo notes, and tradeoffs."
            )

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


def _why_it_matters(
    stage_id: str,
    context: Optional[MissionContext] = None,
) -> str:
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
    base = mapping.get(
        stage_id,
        "This mission moves the project closer to a working portfolio build.",
    )

    if not context:
        return base

    if context.evidence_coverage_state in {"adequate_direct", "adjacent_only", "exploratory"}:
        return (
            f"{base} Because evidence coverage is {context.evidence_coverage_state}, "
            "this mission should make assumptions visible and validation explicit."
        )

    return base


def _commands(
    stage_id: str,
    primary_stack: str,
    context: Optional[MissionContext] = None,
) -> List[str]:
    if context:
        playbook_commands = context.playbook.setup_commands[:3]

        if stage_id == "define":
            return [
                *playbook_commands[:2],
                f"# Scope this mission around: {_anchor_phrase(context)}",
            ]

        if stage_id == "mvp":
            first_file = context.playbook.typical_file_structure[0]
            return [
                f"# Build the first {_anchor_phrase(context)} input-to-output workflow",
                f"# Primary stack to consider: {primary_stack}",
                f"# Start from playbook file or folder: {first_file}",
            ]

        if stage_id == "validate":
            metric = _metric_phrase(context)
            return [
                "mkdir -p tests outputs",
                f"# Validate using: {metric}",
                f"# Save results in: {_first_output_path(context)}",
            ]

        if stage_id == "extend":
            extension = (
                context.advanced_extensions[0]
                if context.advanced_extensions
                else context.playbook.core_concepts[-1]
            )
            return [
                f"# Add one extension only: {extension}",
                "# Re-run the MVP validation before packaging",
            ]

        if stage_id == "package":
            return [
                "touch docs/demo_script.md docs/architecture_notes.md",
                f"# Document demo strategy: {context.playbook.demo_strategy}",
            ]

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


def _expected_outputs(
    stage_id: str,
    project_title: str,
    context: Optional[MissionContext] = None,
) -> List[str]:
    if context:
        if stage_id == "define":
            return [
                f"A scoped {_anchor_phrase(context)} problem statement.",
                f"A documented input list including: {context.playbook.typical_inputs[0]}.",
                f"A success metric based on: {_metric_phrase(context)}.",
            ]

        if stage_id == "mvp":
            return [
                f"A runnable first version of {project_title}.",
                f"One output shaped like: {context.playbook.typical_outputs[0]}.",
                f"A saved artifact at {_first_output_path(context)}.",
            ]

        if stage_id == "validate":
            return [
                f"A validation result for {_metric_phrase(context)}.",
                context.playbook.first_milestone_check,
            ]

        if stage_id == "extend":
            return [
                "One advanced capability connected to the MVP.",
                "A before/after note explaining what improved.",
            ]

        if stage_id == "package":
            return [
                context.playbook.typical_portfolio_artifacts[0],
                "A README section explaining decisions, validation, and limitations.",
                f"A demo following: {context.playbook.demo_strategy}",
            ]

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


def _acceptance_criteria(
    stage: RoadmapStage,
    context: Optional[MissionContext] = None,
) -> List[str]:
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

    if context:
        if stage.id == "define":
            criteria.append(
                f"docs or README contains the {_anchor_phrase(context)} input, output, and success metric."
            )
        if stage.id == "mvp":
            criteria.append(
                f"{_first_output_path(context)} exists after running the first workflow."
            )
        if stage.id == "validate":
            criteria.append(
                f"Validation output contains {_metric_phrase(context)}."
            )

    return criteria


def _validation_checks(
    stage_id: str,
    context: Optional[MissionContext] = None,
) -> List[str]:
    if context:
        if stage_id in {"define", "mvp", "validate"}:
            return context.playbook.validation_checks[:3]
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


def _common_errors(
    stage_id: str,
    context: Optional[MissionContext] = None,
) -> List[str]:
    if context:
        return context.playbook.common_errors[:3]
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


def _portfolio_artifact(
    stage_id: str,
    context: Optional[MissionContext] = None,
) -> str:
    if context:
        if stage_id == "package":
            return context.playbook.typical_portfolio_artifacts[0]
        if stage_id == "validate":
            return _first_output_path(context)
    mapping = {
        "define": "docs/problem_statement.md",
        "mvp": "A runnable MVP commit with setup instructions.",
        "validate": "docs/validation_plan.md and saved outputs.",
        "extend": "A documented advanced feature with before/after notes.",
        "package": "README.md, demo script, architecture notes, and resume bullet.",
    }
    return mapping.get(stage_id, "A saved project artifact.")


def _unlock_condition(
    stage_id: str,
    context: Optional[MissionContext] = None,
) -> str:
    if context:
        if stage_id == "define":
            return (
                f"Unlocks when the {_anchor_phrase(context)} scope has inputs, "
                "outputs, and a measurable success metric."
            )
        if stage_id == "mvp":
            return f"Unlocks when {_first_output_path(context)} is created by the MVP workflow."
        if stage_id == "validate":
            return f"Unlocks when validation checks include {_metric_phrase(context)}."
    mapping = {
        "define": "Unlocks when the project has a narrow problem, input, output, and success metric.",
        "mvp": "Unlocks when the first input-to-output workflow runs.",
        "validate": "Unlocks when validation examples and results are documented.",
        "extend": "Unlocks when one advanced feature is implemented without breaking the MVP.",
        "package": "Unlocks when the project is ready to show publicly.",
    }
    return mapping.get(stage_id, "Unlocks when the mission output is complete.")


def _anchor_phrase(context: MissionContext) -> str:
    concepts = mission_focus_concepts(
        context.planning_concepts
    )

    if concepts:
        return " ".join(
            concept.surface_form
            for concept in concepts[:3]
        )

    return context.project_title


def _domain_focus(context: MissionContext) -> str:
    if context.playbook.core_concepts:
        return context.playbook.core_concepts[0]

    return context.resolved_planning_domain.replace("_", " ")


def _metric_phrase(context: MissionContext) -> str:
    if context.playbook.metrics_to_track:
        return context.playbook.metrics_to_track[0]

    return "validation result"


def _first_output_path(context: MissionContext) -> str:
    for item in context.playbook.typical_file_structure:
        if item.startswith("outputs/"):
            return item

    return "outputs/sample_result.json"
