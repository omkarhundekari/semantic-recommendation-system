from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from planning.mission_context import MissionContext
from schemas.product_models import RoadmapStage


TESTABLE_TERMS = {
    "prints",
    "returns",
    "shows",
    "outputs",
    "passes",
    "contains",
    "exists",
    "creates",
    "saves",
    "runs",
    "loads",
    "renders",
    "responds",
}


@dataclass(frozen=True)
class MissionSpecificityReport:
    passed: bool
    violations: List[str]


def validate_mission_specificity(
    *,
    mission: RoadmapStage,
    context: MissionContext,
) -> MissionSpecificityReport:
    violations = []

    objective = mission.objective or mission.purpose or ""
    combined_text = " ".join(
        [
            mission.title,
            mission.purpose,
            mission.objective or "",
            " ".join(mission.tasks),
            " ".join(mission.commands),
            " ".join(mission.expected_outputs),
            " ".join(mission.acceptance_criteria),
            " ".join(mission.validation_checks),
            mission.portfolio_artifact or "",
            mission.unlock_condition or "",
        ]
    )

    _validate_query_anchor_presence(
        objective=objective,
        context=context,
        violations=violations,
    )
    _validate_expected_outputs(
        mission=mission,
        violations=violations,
    )
    _validate_validation_checks(
        mission=mission,
        violations=violations,
    )
    _validate_acceptance_criteria(
        mission=mission,
        violations=violations,
    )
    _validate_domain_specificity(
        combined_text=combined_text,
        context=context,
        violations=violations,
    )
    _validate_stack_specificity(
        combined_text=combined_text,
        context=context,
        violations=violations,
    )

    return MissionSpecificityReport(
        passed=not violations,
        violations=violations,
    )


def validate_roadmap_specificity(
    *,
    missions: List[RoadmapStage],
    context: MissionContext,
) -> MissionSpecificityReport:
    all_violations = []

    for mission in missions:
        report = validate_mission_specificity(
            mission=mission,
            context=context,
        )

        all_violations.extend(
            f"{mission.id}: {violation}"
            for violation in report.violations
        )

    return MissionSpecificityReport(
        passed=not all_violations,
        violations=all_violations,
    )


def _validate_query_anchor_presence(
    *,
    objective: str,
    context: MissionContext,
    violations: List[str],
) -> None:
    if not context.query_anchors:
        return

    normalized_objective = objective.lower()
    missing_anchors = [
        anchor
        for anchor in context.query_anchors[:3]
        if not _contains_term(normalized_objective, anchor)
    ]

    if missing_anchors:
        violations.append(
            "Objective missing query anchor(s): "
            + ", ".join(missing_anchors)
        )


def _validate_expected_outputs(
    *,
    mission: RoadmapStage,
    violations: List[str],
) -> None:
    if not mission.expected_outputs:
        violations.append("Mission has no expected outputs.")


def _validate_validation_checks(
    *,
    mission: RoadmapStage,
    violations: List[str],
) -> None:
    if not mission.validation_checks:
        violations.append("Mission has no validation checks.")


def _validate_acceptance_criteria(
    *,
    mission: RoadmapStage,
    violations: List[str],
) -> None:
    if not mission.acceptance_criteria:
        violations.append("Mission has no acceptance criteria.")
        return

    weak_criteria = [
        criterion
        for criterion in mission.acceptance_criteria
        if not _is_testable_criterion(criterion)
    ]

    if weak_criteria:
        violations.append(
            "Acceptance criteria may not be testable: "
            + " | ".join(weak_criteria[:2])
        )


def _validate_domain_specificity(
    *,
    combined_text: str,
    context: MissionContext,
    violations: List[str],
) -> None:
    normalized_text = combined_text.lower()
    domain_terms = [
        *context.playbook.core_concepts[:4],
        *context.playbook.typical_file_structure[:4],
        *context.playbook.metrics_to_track[:4],
    ]

    if not domain_terms:
        return

    if not any(term.lower() in normalized_text for term in domain_terms):
        violations.append(
            "Mission does not reference domain-specific playbook signals."
        )


def _validate_stack_specificity(
    *,
    combined_text: str,
    context: MissionContext,
    violations: List[str],
) -> None:
    if not context.primary_stack:
        return

    normalized_text = combined_text.lower()

    if not any(stack.lower() in normalized_text for stack in context.primary_stack):
        violations.append(
            "Mission does not reference the selected or recommended stack."
        )


def _is_testable_criterion(criterion: str) -> bool:
    normalized = criterion.lower()

    return any(term in normalized for term in TESTABLE_TERMS)


def _contains_term(text: str, term: str) -> bool:
    normalized = term.strip().lower()

    if not normalized:
        return True

    if " " in normalized:
        return normalized in text

    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            text,
        )
    )
