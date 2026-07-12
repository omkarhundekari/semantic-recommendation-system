from __future__ import annotations

from typing import List, Optional

from planning.mission_context import MissionContext
from schemas.product_models import GuidedMissionStep, RoadmapStage


def build_guided_steps_for_stage(
    *,
    stage: RoadmapStage,
    context: MissionContext,
) -> List[GuidedMissionStep]:
    if stage.id == "define":
        return _define_steps(context)

    if stage.id == "mvp":
        return _mvp_steps(context)

    if stage.id == "validate":
        return _validate_steps(context)

    if stage.id == "extend":
        return _extend_steps(context)

    if stage.id == "package":
        return _package_steps(context)

    return []


def _define_steps(context: MissionContext) -> List[GuidedMissionStep]:
    primary_files = _starter_files(context)
    command = context.playbook.setup_commands[0] if context.playbook.setup_commands else None

    return [
        GuidedMissionStep(
            step_id="create-project-structure",
            title="Create the project structure",
            explanation=(
                "Before writing features, separate the project into folders for "
                "inputs, code, tests, and saved outputs. This makes the build easier "
                "to debug and explain."
            ),
            action="Create the first folders and files for this project.",
            starter_command=command,
            starter_files=primary_files,
            done_when=(
                "The starter folders or files exist in your repository and match "
                "the project domain."
            ),
            common_confusion=(
                "Do not mix source inputs, generated outputs, and code in the same "
                "folder. That makes validation harder later."
            ),
            decision_point=_decision_point(
                context,
                "Why is this file or folder structure useful for your project?",
            ),
            proof_type="folder_confirm",
            proof_prompt=(
                "Paste your folder tree or list the files you created for this step."
            ),
            expected_output_patterns=_expected_patterns_from_files(primary_files),
            interview_takeaway=(
                "I structured the project so inputs, code, tests, and outputs were "
                "separated before implementation."
            ),
        ),
        GuidedMissionStep(
            step_id="write-scope",
            title="Write the project scope",
            explanation=(
                "A strong project starts with a narrow input, output, and success "
                "metric. This prevents the build from becoming a vague demo."
            ),
            action=(
                f"Write a short scope for {_anchor_phrase(context)} with one input, "
                "one output, and one success metric."
            ),
            starter_command="touch docs/problem_statement.md",
            starter_files=["docs/problem_statement.md"],
            done_when=(
                "docs/problem_statement.md explains the user, input, output, and "
                "success metric in plain language."
            ),
            common_confusion=(
                "A topic is not a scope. A scope must say what the system receives "
                "and what it produces."
            ),
            decision_point=_decision_point(
                context,
                f"Why is {_metric_phrase(context)} a useful success signal here?",
            ),
            proof_type="explanation",
            proof_prompt=(
                "Write one sentence explaining what your project receives, produces, "
                "and how you will know it works."
            ),
            expected_output_patterns=[],
            interview_takeaway=(
                "I defined the project around measurable inputs and outputs instead "
                "of only describing the topic."
            ),
        ),
    ]


def _mvp_steps(context: MissionContext) -> List[GuidedMissionStep]:
    output_path = _first_output_path(context)

    return [
        GuidedMissionStep(
            step_id="build-first-workflow",
            title="Build the first input-to-output workflow",
            explanation=(
                "The MVP should prove one complete path works before you add advanced "
                "features. A tiny working loop is better than many disconnected files."
            ),
            action=(
                f"Create the smallest workflow that turns one {_domain_input(context)} "
                f"into one {_domain_output(context)}."
            ),
            starter_command=_mvp_command(context),
            starter_files=[] if _is_intermediate_or_advanced(context) else _starter_files(context),
            done_when=(
                f"Running the workflow creates or prints one meaningful output for "
                f"{_anchor_phrase(context)}."
            ),
            common_confusion=(
                "Do not build the advanced version first. Make one boring example run "
                "end to end, then improve it."
            ),
            decision_point=_decision_point(
                context,
                "What did you intentionally leave out of the MVP, and why?",
            ),
            proof_type="output_paste",
            proof_prompt=(
                "Paste the first output from your workflow. Include the input you used "
                "and the output it produced."
            ),
            expected_output_patterns=_mvp_expected_patterns(context),
            interview_takeaway=(
                "I built the smallest complete workflow first so every later feature "
                "had a stable foundation."
            ),
        ),
        GuidedMissionStep(
            step_id="save-mvp-output",
            title="Save the MVP output",
            explanation=(
                "Saved outputs become proof that the system worked at a specific point "
                "in time. This helps with debugging, validation, and portfolio evidence."
            ),
            action=f"Save one successful MVP result to {output_path}.",
            starter_command=f"mkdir -p outputs && touch {output_path}",
            starter_files=[output_path],
            done_when=f"{output_path} contains one real result from your MVP workflow.",
            common_confusion=(
                "A screenshot is useful later, but save a text or JSON output first so "
                "the result is easy to inspect."
            ),
            decision_point=_decision_point(
                context,
                "What does this output prove about your MVP?",
            ),
            proof_type="output_paste",
            proof_prompt=f"Paste the saved result from {output_path}.",
            expected_output_patterns=_mvp_expected_patterns(context),
            interview_takeaway=(
                "I saved concrete MVP outputs so I could compare later improvements "
                "against the first working version."
            ),
        ),
    ]


def _validate_steps(context: MissionContext) -> List[GuidedMissionStep]:
    metric = _metric_phrase(context)
    output_path = _first_output_path(context)

    return [
        GuidedMissionStep(
            step_id="run-validation",
            title="Run one validation check",
            explanation=(
                "Validation turns a working demo into an engineering project. It shows "
                "what works, what fails, and what still needs improvement."
            ),
            action=f"Run one validation check using {metric}.",
            starter_command="mkdir -p tests outputs",
            starter_files=["tests/", "outputs/"],
            done_when=f"You have one saved validation result that mentions {metric}.",
            common_confusion=(
                "Validation is not only proving success. A useful validation step also "
                "reveals at least one limitation."
            ),
            decision_point=_decision_point(
                context,
                f"Why did you choose {metric} instead of a simpler pass/fail check?",
            ),
            proof_type="output_paste",
            proof_prompt=(
                "Paste your validation output. Include the metric name, test input, "
                "and observed result."
            ),
            expected_output_patterns=[metric],
            interview_takeaway=(
                "I validated the project with a measurable signal instead of only "
                "claiming the demo worked."
            ),
        ),
        GuidedMissionStep(
            step_id="document-failure",
            title="Document one failure case",
            explanation=(
                "Interviewers trust projects more when you can explain where they fail. "
                "A known limitation shows engineering maturity."
            ),
            action="Write down one case where the project gives a weak or incomplete result.",
            starter_command="touch docs/validation_notes.md",
            starter_files=["docs/validation_notes.md"],
            done_when=(
                "docs/validation_notes.md contains one failure case and one possible fix."
            ),
            common_confusion=(
                "A limitation does not make the project bad. It makes your explanation "
                "more honest and credible."
            ),
            decision_point=_decision_point(
                context,
                "What would you improve first if you had one more week?",
            ),
            proof_type="explanation",
            proof_prompt=(
                "Write one failure case, why it happened, and what you would improve."
            ),
            expected_output_patterns=[],
            interview_takeaway=(
                "I tested the project beyond the happy path and documented a realistic "
                "next improvement."
            ),
        ),
    ]


def _extend_steps(context: MissionContext) -> List[GuidedMissionStep]:
    extension = (
        context.advanced_extensions[0]
        if context.advanced_extensions
        else "one advanced capability"
    )

    return [
        GuidedMissionStep(
            step_id="choose-one-extension",
            title="Choose one extension",
            explanation=(
                "Advanced features are useful only after the MVP is stable. Pick one "
                "extension that improves the project without changing the whole design."
            ),
            action=f"Add only this extension: {extension}.",
            starter_command=None,
            starter_files=[],
            done_when="The extension works without breaking the original MVP workflow.",
            common_confusion=(
                "Do not add three extensions at once. If something breaks, you will not "
                "know which change caused it."
            ),
            decision_point=_decision_point(
                context,
                "Why is this extension the best next improvement?",
            ),
            proof_type="explanation",
            proof_prompt=(
                "Explain what the extension changes and how you confirmed the MVP still works."
            ),
            expected_output_patterns=[],
            interview_takeaway=(
                "I improved the MVP with one focused extension while preserving the "
                "original workflow."
            ),
        )
    ]


def _package_steps(context: MissionContext) -> List[GuidedMissionStep]:
    return [
        GuidedMissionStep(
            step_id="write-portfolio-summary",
            title="Write the portfolio summary",
            explanation=(
                "A finished project needs a clear story. The README should explain what "
                "you built, why it matters, how to run it, and what tradeoffs you made."
            ),
            action="Write the README summary, setup instructions, validation result, and limitations.",
            starter_command="touch docs/demo_script.md docs/architecture_notes.md",
            starter_files=["README.md", "docs/demo_script.md", "docs/architecture_notes.md"],
            done_when=(
                "A reader can understand the project, run it, and see one validation result "
                "without asking you for context."
            ),
            common_confusion=(
                "Do not write only a feature list. Explain the decisions and evidence behind "
                "the build."
            ),
            decision_point=_decision_point(
                context,
                "What is the strongest technical decision you made in this project?",
            ),
            proof_type="explanation",
            proof_prompt=(
                "Write the interview explanation for this project in three sentences."
            ),
            expected_output_patterns=[],
            interview_takeaway=(
                "I can explain the project as a complete engineering story: problem, design, "
                "validation, tradeoffs, and next steps."
            ),
        )
    ]


def _starter_files(context: MissionContext) -> List[str]:
    return context.playbook.typical_file_structure[:4]


def _expected_patterns_from_files(files: List[str]) -> List[str]:
    return [
        item.strip("/").split("/")[0]
        for item in files
        if item.strip("/")
    ]


def _anchor_phrase(context: MissionContext) -> str:
    if context.query_anchors:
        return " ".join(context.query_anchors[:3])

    return context.project_title


def _metric_phrase(context: MissionContext) -> str:
    if context.playbook.metrics_to_track:
        return context.playbook.metrics_to_track[0]

    return "validation result"


def _first_output_path(context: MissionContext) -> str:
    for item in context.playbook.typical_file_structure:
        if item.startswith("outputs/"):
            return item

    return "outputs/sample_result.json"


def _domain_input(context: MissionContext) -> str:
    if context.playbook.typical_inputs:
        return context.playbook.typical_inputs[0]

    return "input"


def _domain_output(context: MissionContext) -> str:
    if context.playbook.typical_outputs:
        return context.playbook.typical_outputs[0]

    return "output"


def _mvp_command(context: MissionContext) -> Optional[str]:
    if "frontend" in context.resolved_planning_domain:
        return "cd frontend && npm run dev"

    if context.primary_stack and any(item.lower() == "python" for item in context.primary_stack):
        return "python src/main.py"

    return None


def _mvp_expected_patterns(context: MissionContext) -> List[str]:
    if context.resolved_planning_domain == "rag_llm":
        return ["Query", "Retrieved", "Score"]

    if context.resolved_planning_domain == "frontend":
        return ["loading", "error", "success"]

    if context.resolved_planning_domain == "education_tech":
        return ["learner", "activity", "feedback"]

    return ["output"]


def _decision_point(context: MissionContext, prompt: str) -> Optional[str]:
    if context.skill_level.lower() == "beginner":
        return None

    return prompt


def _is_intermediate_or_advanced(context: MissionContext) -> bool:
    return context.skill_level.lower() in {"intermediate", "advanced"}
