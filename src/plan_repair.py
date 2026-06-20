from copy import deepcopy
from typing import Dict, List, Tuple

from constraint_adapter import apply_constraints_to_idea, parse_time_available
from plan_verifier import verify_project_ideas


def narrow_mvp_for_short_timeline(
    mvp_scope: List[str],
) -> List[str]:
    narrowed = list(mvp_scope[:4])

    scope_step = (
        "Document the intentionally constrained MVP and defer advanced "
        "automation, integrations, and polish to a later iteration."
    )

    if scope_step not in narrowed:
        narrowed.append(scope_step)

    return narrowed


def repair_project_plan(
    idea: Dict,
    constraints: Dict,
) -> Tuple[Dict, List[str], Dict]:
    """
    Applies only deterministic, low-risk repairs.

    It does not invent evidence or silently rename duplicate directions.
    Those cases remain visible for later regeneration by an LLM planner.
    """
    repaired = deepcopy(idea)
    repairs = []

    original_stack = repaired.get("suggested_tech_stack", [])
    cleaned_stack = [
        item
        for item in original_stack
        if str(item).strip().lower() != "streamlit"
    ]

    if len(cleaned_stack) != len(original_stack):
        repaired["suggested_tech_stack"] = cleaned_stack
        repairs.append("Removed prototype-only Streamlit dependency.")

    repaired = apply_constraints_to_idea(repaired, constraints)

    available_days = parse_time_available(
        constraints.get("time_available")
    )

    verification = verify_project_ideas(
        [repaired],
        constraints,
    )[0]

    if (
        available_days
        and available_days <= 7
        and not verification["checks"]["time_feasibility"]
    ):
        repaired["mvp_scope"] = narrow_mvp_for_short_timeline(
            repaired.get("mvp_scope", [])
        )
        repairs.append(
            "Narrowed the MVP to fit a short timeline."
        )

        repaired["feasibility_analysis"] = {
            **repaired.get("feasibility_analysis", {}),
            "build_profile": {
                "scope": "Focused",
                "estimated_effort": "3–5 days",
                "reason": (
                    "The MVP was intentionally narrowed for the stated "
                    "short timeline."
                ),
            },
        }

        verification = verify_project_ideas(
            [repaired],
            constraints,
        )[0]

    return repaired, repairs, verification
