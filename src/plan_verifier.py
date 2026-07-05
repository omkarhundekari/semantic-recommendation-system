from typing import Dict, List

from constraint_adapter import parse_time_available


GENERIC_PHRASES = [
    "simple input form",
    "csv-backed prototype",
    "core workflow for",
]

BANNED_STACK_TERMS = {
    "streamlit",
}


def _normalize_text(value) -> str:
    return " ".join(str(value or "").lower().split())


def _token_set(value: str) -> set:
    return {
        token.strip(".,:;!?()[]{}")
        for token in _normalize_text(value).split()
        if len(token.strip(".,:;!?()[]{}")) >= 3
    }


def _estimated_max_days(value: str) -> int:
    """
    Extract the upper bound from a feasibility build-time range.

    Supports normal hyphens, en dashes, and strings such as "10–16 days".
    Returns zero only when the value has no usable numeric estimate.
    """
    import re

    numbers = [
        int(number)
        for number in re.findall(r"\d+", _normalize_text(value))
    ]

    return max(numbers) if numbers else 0


def _is_duplicate(candidate: Dict, other: Dict) -> bool:
    candidate_tokens = _token_set(candidate.get("project_title", ""))
    other_tokens = _token_set(other.get("project_title", ""))

    if not candidate_tokens or not other_tokens:
        return False

    overlap = len(candidate_tokens & other_tokens)
    union = len(candidate_tokens | other_tokens)

    return union > 0 and overlap / union >= 0.75


def verify_project_ideas(
    ideas: List[Dict],
    constraints: Dict,
) -> List[Dict]:
    target_roles = [
        _normalize_text(role)
        for role in constraints.get("target_roles", [])
        if role
    ]
    preferred_stack = [
        _normalize_text(item)
        for item in constraints.get("preferred_stack", [])
        if item
    ]
    available_days = parse_time_available(
        constraints.get("time_available")
    )

    results = []

    for index, idea in enumerate(ideas):
        title = idea.get("project_title", "Untitled project")
        stack = [
            _normalize_text(item)
            for item in idea.get("suggested_tech_stack", [])
        ]
        mvp_text = " ".join(idea.get("mvp_scope", []))
        combined_text = _normalize_text(
            " ".join(
                [
                    title,
                    idea.get("idea_angle", ""),
                    idea.get("research_motivation", ""),
                    mvp_text,
                ]
            )
        )

        build_profile = (
            idea.get("feasibility_analysis", {})
            .get("build_profile", {})
        )
        estimated_effort = build_profile.get(
            "estimated_effort",
            ""
        )

        role_match = (
            not target_roles
            or any(
                role in _normalize_text(
                    " ".join(idea.get("target_roles", []))
                )
                for role in target_roles
            )
        )

        stack_match = (
            not preferred_stack
            or any(item in stack for item in preferred_stack)
        )

        evidence_present = bool(
            idea.get("evidence_title")
            and idea.get("evidence_source_type")
        )

        no_banned_stack = not any(
            item in BANNED_STACK_TERMS
            for item in stack
        )

        no_generic_mvp = not any(
            phrase in combined_text
            for phrase in GENERIC_PHRASES
        )

        within_time = True
        if available_days:
            estimated_days = _estimated_max_days(estimated_effort)
            within_time = (
                estimated_days == 0
                or estimated_days <= available_days
            )

        distinct = not any(
            _is_duplicate(idea, other)
            for other_index, other in enumerate(ideas)
            if other_index != index
        )

        checks = {
            "role_alignment": role_match,
            "preferred_stack_alignment": stack_match,
            "evidence_present": evidence_present,
            "no_banned_stack": no_banned_stack,
            "specific_mvp_language": no_generic_mvp,
            "time_feasibility": within_time,
            "direction_is_distinct": distinct,
        }

        score = sum(checks.values())
        warnings = []

        if not role_match:
            warnings.append(
                "The direction does not clearly match the requested target role."
            )

        if not stack_match:
            warnings.append(
                "The preferred technology stack is not reflected in the direction."
            )

        if not evidence_present:
            warnings.append(
                "The direction has no visible evidence reference."
            )

        if not no_banned_stack:
            warnings.append(
                "The direction contains a prototype-only stack dependency."
            )

        if not no_generic_mvp:
            warnings.append(
                "The MVP still contains generic template language."
            )

        if not within_time:
            warnings.append(
                "The estimated effort exceeds the stated timeline."
            )

        if not distinct:
            warnings.append(
                "This direction overlaps too heavily with another recommendation."
            )

        results.append(
            {
                "status": "passed" if not warnings else "needs_review",
                "score": score,
                "max_score": len(checks),
                "checks": checks,
                "warnings": warnings,
            }
        )

    return results
