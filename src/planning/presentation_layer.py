from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class PresentationProjectDirection:
    title: str
    level: str
    estimated_time: str
    what_you_will_build: str
    why_it_matters: str
    skills_shown: list[str]
    interview_talking_point: str
    evidence_badge: str
    confidence_explanation: str
    open_questions: list[str]
    evidence_summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_presentation_project_directions(
    *,
    parsed_response: dict[str, Any],
    evidence_cards: list[Any],
    preview_validation: Any,
) -> list[dict[str, Any]]:
    if not preview_validation.is_valid:
        return []

    project_directions = parsed_response.get("project_directions", [])
    if not isinstance(project_directions, list):
        return []

    presentations = []
    for direction in project_directions:
        if not isinstance(direction, dict):
            continue

        presentation = to_presentation_project_direction(
            direction=direction,
            evidence_cards=evidence_cards,
        )
        presentations.append(presentation.to_dict())

    return presentations


def to_presentation_project_direction(
    *,
    direction: dict[str, Any],
    evidence_cards: list[Any],
) -> PresentationProjectDirection:
    confidence = str(direction.get("evidence_confidence", "Exploratory"))
    cited_cards = _cards_for_direction(
        evidence_cards=evidence_cards,
        source_ids=direction.get("source_ids", []),
    )

    return PresentationProjectDirection(
        title=_derive_presentation_title(direction),
        level=_derive_level(direction),
        estimated_time=str(direction.get("estimated_time", "Flexible")),
        what_you_will_build=_derive_what_you_will_build(direction),
        why_it_matters=_derive_why_it_matters(direction),
        skills_shown=_derive_skills_shown(direction),
        interview_talking_point=_derive_interview_talking_point(direction),
        evidence_badge=_derive_evidence_badge(confidence, cited_cards),
        confidence_explanation=_derive_confidence_explanation(
            confidence,
            cited_cards,
        ),
        open_questions=_derive_open_questions(direction, confidence),
        evidence_summary=_derive_evidence_summary(cited_cards),
    )


def _cards_for_direction(
    *,
    evidence_cards: list[Any],
    source_ids: list[Any],
) -> list[Any]:
    source_id_set = {str(source_id) for source_id in source_ids}
    return [
        card
        for card in evidence_cards
        if str(getattr(card, "source_id", "")) in source_id_set
    ]


def _derive_presentation_title(direction: dict[str, Any]) -> str:
    raw_title = str(direction.get("title", "Project Direction")).strip()

    prefixes = {
        "Quick Evidence Trace: ": "Starter",
        "Evidence-Grounded MVP: ": "MVP",
        "Validation-Safe Project Engine: ": "Engine",
    }

    for prefix, suffix in prefixes.items():
        if raw_title.startswith(prefix):
            base_title = raw_title.replace(prefix, "", 1).strip()
            return f"{base_title} {suffix}"

    return raw_title


def _derive_level(direction: dict[str, Any]) -> str:
    scope_level = direction.get("scope_level")
    if scope_level == "easy":
        return "Beginner"
    if scope_level == "medium":
        return "Intermediate"
    if scope_level == "hard":
        return "Advanced"
    return "Flexible"


def _derive_what_you_will_build(direction: dict[str, Any]) -> str:
    mvp_scope = direction.get("mvp_scope", [])
    if isinstance(mvp_scope, list) and mvp_scope:
        steps = [str(step) for step in mvp_scope[:3]]
        return "You will build " + "; ".join(steps) + "."

    problem_statement = direction.get("problem_statement")
    if problem_statement:
        return str(problem_statement)

    return (
        "You will build a focused, evidence-grounded project that can be "
        "shown in a portfolio and discussed in interviews."
    )


def _derive_why_it_matters(direction: dict[str, Any]) -> str:
    grounded_reason = direction.get("why_this_is_grounded")
    if grounded_reason:
        return str(grounded_reason)

    return (
        "This project is connected to real research or implementation signals, "
        "so it is stronger than a generic tutorial project."
    )


def _derive_skills_shown(direction: dict[str, Any]) -> list[str]:
    skills = direction.get("skills_demonstrated", [])
    if isinstance(skills, list) and skills:
        return [str(skill) for skill in skills[:5]]

    return [
        "Evidence-grounded product planning",
        "Backend API design",
        "Evaluation and validation",
    ]


def _derive_interview_talking_point(direction: dict[str, Any]) -> str:
    talking_points = direction.get("interview_talking_points", [])
    if isinstance(talking_points, list) and talking_points:
        return str(talking_points[0])

    resume_bullet = direction.get("resume_bullet")
    if resume_bullet:
        return str(resume_bullet)

    return (
        "I built this project by turning evidence from research and real "
        "implementation patterns into a validated product direction."
    )


def _derive_evidence_badge(
    confidence: str,
    cited_cards: list[Any],
) -> str:
    source_types = {
        str(getattr(card, "source_type", ""))
        for card in cited_cards
    }

    if confidence == "Strong":
        if (
            "research_paper" in source_types
            and "github_repository" in source_types
        ):
            return "Strong research and implementation support"
        if "research_paper" in source_types:
            return "Strong research support"
        if "github_repository" in source_types:
            return "Backed by implementation patterns"
        return "Strong evidence support"

    if confidence == "Limited":
        return "Limited but usable evidence"

    return "Exploratory — open research area"


def _derive_confidence_explanation(
    confidence: str,
    cited_cards: list[Any],
) -> str:
    evidence_summary = _derive_evidence_summary(cited_cards)

    if confidence == "Strong":
        return (
            f"This direction is well supported by available evidence: "
            f"{evidence_summary.lower()}."
        )

    if confidence == "Limited":
        return (
            "This direction has some supporting evidence, but you should "
            "treat parts of the project scope as assumptions to validate."
        )

    return (
        "This direction is exploratory, which means it may be more original, "
        "but you will need to define and validate the approach carefully."
    )


def _derive_open_questions(
    direction: dict[str, Any],
    confidence: str,
) -> list[str]:
    warnings = direction.get("grounding_warnings", [])
    if isinstance(warnings, list) and warnings:
        return [
            "Clarify how the weaker evidence should shape the project scope."
        ]

    if confidence == "Strong":
        return []

    if confidence == "Limited":
        return [
            "Which parts of the idea are directly supported versus inferred?",
            "What small prototype can validate the riskiest assumption first?",
        ]

    return [
        "What evidence would prove this idea is useful?",
        "Which narrow user problem should the first prototype focus on?",
    ]


def _derive_evidence_summary(cited_cards: list[Any]) -> str:
    if not cited_cards:
        return "Supported by internal evidence checks"

    research_count = sum(
        1
        for card in cited_cards
        if getattr(card, "source_type", None) == "research_paper"
    )
    github_count = sum(
        1
        for card in cited_cards
        if getattr(card, "source_type", None) == "github_repository"
    )
    pattern_count = sum(
        1
        for card in cited_cards
        if getattr(card, "source_type", None) == "project_pattern"
    )

    parts = []
    if research_count:
        label = "research paper" if research_count == 1 else "research papers"
        parts.append(f"{research_count} {label}")
    if github_count:
        label = (
            "GitHub implementation"
            if github_count == 1
            else "GitHub implementations"
        )
        parts.append(f"{github_count} {label}")
    if pattern_count:
        label = "project pattern" if pattern_count == 1 else "project patterns"
        parts.append(f"{pattern_count} {label}")

    if not parts:
        label = "evidence source" if len(cited_cards) == 1 else "evidence sources"
        return f"Supported by {len(cited_cards)} {label}"

    return "Supported by " + " and ".join(parts)
