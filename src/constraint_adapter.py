import re
from typing import Dict, List


ML_MVP_TEMPLATES = {
    "model evaluation intelligence dashboard": [
        "Choose one public classification dataset and train two baseline models.",
        "Compare accuracy, precision, recall, F1 score, and calibration across both models.",
        "Add an error-slice view for important subgroups, predicted classes, or confidence ranges.",
        "Show feature importance or model explanations for selected predictions.",
        "Save experiment configuration, dataset version, metrics, and model artifacts for reproducibility.",
        "Expose the comparison results through a FastAPI endpoint and a simple portfolio-ready dashboard.",
    ],
    "ml prediction monitoring platform": [
        "Train or load one baseline prediction model using a public dataset.",
        "Simulate incoming inference batches with timestamps, predictions, and ground-truth labels.",
        "Track prediction quality, feature distributions, prediction distributions, and error rates over time.",
        "Detect simple data drift or prediction drift using transparent statistical thresholds.",
        "Show alert states, trend charts, and affected features in a monitoring dashboard.",
        "Store each monitoring run so users can compare model behavior across time windows.",
    ],
    "explainable ml decision assistant": [
        "Train or load one prediction model on a public, non-sensitive dataset.",
        "Accept a single prediction input and return the prediction, confidence, and key feature contributions.",
        "Generate a plain-language explanation of why the model produced the result.",
        "Flag low-confidence or out-of-distribution inputs with a visible warning state.",
        "Compare explanations across multiple examples to surface inconsistent or risky behavior.",
        "Document limitations so users do not treat the prototype as a high-stakes decision system.",
    ],
}


def parse_time_available(value) -> int:
    text = str(value or "").lower().strip()

    if not text:
        return 0

    if "weekend" in text:
        return 2

    match = re.search(r"(\d+)\s*(day|days|week|weeks|month|months)", text)
    if not match:
        return 0

    amount = int(match.group(1))
    unit = match.group(2)

    if "week" in unit:
        return amount * 7

    if "month" in unit:
        return amount * 30

    return amount


def has_ml_target_role(target_roles: List[str]) -> bool:
    role_text = " ".join(str(role).lower() for role in target_roles)

    return any(
        term in role_text
        for term in [
            "ml engineer",
            "machine learning engineer",
            "ai engineer",
            "applied ml",
            "data scientist",
        ]
    )


def deduplicate(items: List[str]) -> List[str]:
    unique_items = []
    seen = set()

    for item in items:
        clean_item = str(item).strip()
        key = clean_item.lower()

        if clean_item and key not in seen:
            seen.add(key)
            unique_items.append(clean_item)

    return unique_items


def apply_constraints_to_idea(
    idea: Dict,
    constraints: Dict,
) -> Dict:
    updated = dict(idea)

    target_roles = constraints.get("target_roles", []) or []
    preferred_stack = constraints.get("preferred_stack", []) or []
    skill_level = constraints.get("skill_level")
    time_available = constraints.get("time_available")
    available_days = parse_time_available(time_available)

    title = str(updated.get("project_title", "")).lower()
    mvp_scope = list(updated.get("mvp_scope", []))
    tech_stack = list(updated.get("suggested_tech_stack", []))

    if has_ml_target_role(target_roles):
        for title_key, template in ML_MVP_TEMPLATES.items():
            if title_key in title:
                mvp_scope = list(template)
                break

    if available_days and available_days <= 7:
        mvp_scope = mvp_scope[:4]
        mvp_scope.append(
            "Write a focused README that explains the constrained MVP, test data, and known limitations."
        )

    elif available_days >= 14:
        portfolio_steps = [
            "Add automated tests for one critical data-processing or evaluation path.",
            "Containerize the service and provide a reproducible local setup command.",
        ]

        for step in portfolio_steps:
            if step not in mvp_scope:
                mvp_scope.append(step)

    normalized_stack = [item.lower() for item in tech_stack]

    if "streamlit" in normalized_stack and "streamlit" not in [
        str(item).lower() for item in preferred_stack
    ]:
        tech_stack = [
            item for item in tech_stack
            if str(item).lower() != "streamlit"
        ]
        tech_stack.append("React")

    tech_stack.extend(preferred_stack)

    updated["mvp_scope"] = deduplicate(mvp_scope)
    updated["suggested_tech_stack"] = deduplicate(tech_stack)

    summary_parts = []

    if target_roles:
        summary_parts.append(
            "Designed to demonstrate skills relevant to "
            + ", ".join(target_roles[:2])
            + "."
        )

    if time_available:
        summary_parts.append(
            f"Scoped for the stated {time_available} timeline."
        )

    if preferred_stack:
        summary_parts.append(
            "Prioritizes "
            + ", ".join(preferred_stack[:3])
            + " where it fits the project."
        )

    if skill_level:
        skill_text = str(skill_level).strip()
        article = "an" if skill_text[:1].lower() in "aeiou" else "a"

        summary_parts.append(
            f"Assumes {article} {skill_text} starting level."
        )

    updated["constraint_summary"] = " ".join(summary_parts)

    return updated
