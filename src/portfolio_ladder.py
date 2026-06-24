from copy import deepcopy
from typing import Dict, List


LADDER_PROFILES = [
    {
        "tier": "Quick Win",
        "difficulty": "Easy",
        "scope": "Focused",
        "estimated_effort": "3–5 days",
        "reason": (
            "A narrow, polished workflow that is fast to finish, demo, "
            "and explain clearly in an interview."
        ),
    },
    {
        "tier": "Portfolio Build",
        "difficulty": "Medium",
        "scope": "Balanced",
        "estimated_effort": "7–10 days",
        "reason": (
            "A complete end-to-end project with validation, stronger engineering "
            "signals, and meaningful portfolio polish."
        ),
    },
    {
        "tier": "Flagship Challenge",
        "difficulty": "Hard",
        "scope": "Ambitious",
        "estimated_effort": "12–18 days",
        "reason": (
            "A deeper system with stronger evaluation, reliability, "
            "architecture, and deployment-ready signals."
        ),
    },
]


def unique_items(items: List[str]) -> List[str]:
    seen = set()
    result = []

    for item in items:
        clean_item = str(item).strip()
        key = clean_item.lower()

        if clean_item and key not in seen:
            seen.add(key)
            result.append(clean_item)

    return result


def build_easy_scope(mvp_steps: List[str]) -> List[str]:
    steps = mvp_steps[:4]

    steps.append(
        "Run the end-to-end workflow on representative sample data and "
        "document one domain-relevant success metric."
    )

    return unique_items(steps[:5])


def build_medium_scope(mvp_steps: List[str]) -> List[str]:
    steps = [
        step
        for step in mvp_steps[:6]
        if "automated test" not in step.lower()
    ]

    steps.append(
        "Add automated tests for one critical domain workflow and one "
        "invalid-input or failure case."
    )

    return unique_items(steps[:7])


def build_hard_scope(mvp_steps: List[str]) -> List[str]:
    steps = [
        step
        for step in mvp_steps[:7]
        if "automated test" not in step.lower()
    ]

    steps.extend(
        [
            "Add automated tests for core workflows, invalid inputs, and expected failure cases.",
            "Containerize the application with a reproducible local setup.",
            (
                "Add an evaluation, monitoring, or reliability view that "
                "demonstrates system quality."
            ),
        ]
    )

    return unique_items(steps[:10])


def apply_portfolio_ladder(ideas: List[Dict]) -> List[Dict]:
    laddered_ideas = []

    for index, idea in enumerate(ideas):
        updated_idea = deepcopy(idea)

        profile = LADDER_PROFILES[
            min(index, len(LADDER_PROFILES) - 1)
        ]

        original_mvp_steps = list(updated_idea.get("mvp_scope", []))
        extensions = list(updated_idea.get("advanced_extensions", []))

        if profile["difficulty"] == "Easy":
            final_mvp_steps = build_easy_scope(original_mvp_steps)

        elif profile["difficulty"] == "Medium":
            final_mvp_steps = build_medium_scope(original_mvp_steps)

        else:
            final_mvp_steps = build_hard_scope(original_mvp_steps)

            extensions.append(
                (
                    "Add historical run comparison, version tracking, or "
                    "observability after the core workflow is stable."
                )
            )

        updated_idea["mvp_scope"] = final_mvp_steps
        updated_idea["advanced_extensions"] = unique_items(extensions)

        previous_feasibility = updated_idea.get(
            "feasibility_analysis",
            {},
        )

        updated_idea["feasibility_analysis"] = {
            **previous_feasibility,
            "build_profile": {
                "tier": profile["tier"],
                "difficulty": profile["difficulty"],
                "scope": profile["scope"],
                "estimated_effort": profile["estimated_effort"],
                "reason": profile["reason"],
            },
        }

        laddered_ideas.append(updated_idea)

    return laddered_ideas