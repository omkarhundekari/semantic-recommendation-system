from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planning.domain_playbook_loader import DomainPlaybook, load_playbook_or_generic
from query_semantic_projections import (
    PlanningConcept,
    PlanningSemanticProjection,
    available_skills,
    learning_targets,
    required_stack,
    target_roles as semantic_target_role_concepts,
)



@dataclass(frozen=True)
class MissionContext:
    user_goal: str
    project_title: str
    project_summary: str
    resolved_planning_domain: str
    skill_level: str
    timeline: str
    preferred_stack: List[str]
    target_roles: List[str]
    evidence_coverage_state: str
    mvp_steps: List[str]
    advanced_extensions: List[str]
    warnings: List[str]
    playbook: DomainPlaybook
    timeline_bucket: str
    primary_stack: List[str] = field(default_factory=list)
    planning_concepts: tuple[PlanningConcept, ...] = field(default_factory=tuple)
    requested_stack: List[str] = field(default_factory=list)
    learning_targets: List[str] = field(default_factory=list)
    available_skills: List[str] = field(default_factory=list)
    semantic_target_roles: List[str] = field(default_factory=list)


def build_mission_context(
    *,
    idea: Dict[str, Any],
    user_goal: str,
    resolved_planning_domain: Optional[str],
    planning_semantics: PlanningSemanticProjection,
    constraints: Optional[Dict[str, Any]] = None,
    evidence_coverage: Optional[Dict[str, Any]] = None,
) -> MissionContext:
    safe_constraints = constraints or {}
    safe_coverage = evidence_coverage or {}

    domain = (
        resolved_planning_domain
        or str(idea.get("detected_domain", "") or "").strip()
        or "generic"
    )

    preferred_stack = _as_string_list(safe_constraints.get("preferred_stack"))

    semantic_requested_stack = _concept_surfaces(
        required_stack(planning_semantics)
    )
    requested_stack = resolve_requested_stack(
        preferred_stack=preferred_stack,
        semantic_requested_stack=semantic_requested_stack,
    )

    learning_stack = _concept_surfaces(
        learning_targets(planning_semantics)
    )
    held_skills = _concept_surfaces(
        available_skills(planning_semantics)
    )
    semantic_roles = _concept_surfaces(
        semantic_target_role_concepts(planning_semantics)
    )

    suggested_stack = _as_string_list(
        idea.get("suggested_tech_stack")
    )

    primary_stack = resolve_primary_stack(
        requested_stack=requested_stack,
        suggested_stack=suggested_stack,
    )

    return MissionContext(
        user_goal=user_goal,
        project_title=str(idea.get("project_title", "") or "Project Direction"),
        project_summary=str(
            idea.get("project_summary", "")
            or idea.get("idea_angle", "")
            or idea.get("evidence_focus_statement", "")
            or ""
        ),
        resolved_planning_domain=domain,
        skill_level=str(safe_constraints.get("skill_level") or "intermediate"),
        timeline=str(safe_constraints.get("time_available") or "2-3 weeks"),
        timeline_bucket=_bucket_timeline(
            str(safe_constraints.get("time_available") or "2-3 weeks")
        ),
        preferred_stack=preferred_stack,
        target_roles=_as_string_list(safe_constraints.get("target_roles")),
        evidence_coverage_state=str(
            safe_coverage.get("coverage_state") or "unknown"
        ),
        mvp_steps=_as_string_list(idea.get("mvp_scope")),
        advanced_extensions=_as_string_list(idea.get("advanced_extensions")),
        warnings=_as_string_list(safe_coverage.get("warnings")),
        playbook=load_playbook_or_generic(domain),
        primary_stack=primary_stack,
        planning_concepts=tuple(
            planning_semantics.presentation_order
        ),
        requested_stack=requested_stack,
        learning_targets=learning_stack,
        available_skills=held_skills,
        semantic_target_roles=semantic_roles,
    )


def _as_string_list(value: Any) -> List[str]:
    if not value:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    return [str(value).strip()] if str(value).strip() else []


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    deduped = []

    for item in items:
        key = item.lower()
        if key in seen:
            continue

        seen.add(key)
        deduped.append(item)

    return deduped




def _concept_surfaces(
    concepts: tuple[PlanningConcept, ...],
) -> List[str]:
    return [
        concept.surface_form
        for concept in concepts
        if concept.surface_form.strip()
    ]


def resolve_requested_stack(
    *,
    preferred_stack: List[str],
    semantic_requested_stack: List[str],
) -> List[str]:
    return _dedupe_preserve_order(
        preferred_stack + semantic_requested_stack
    )


def resolve_primary_stack(
    *,
    requested_stack: List[str],
    suggested_stack: List[str],
) -> List[str]:
    return _dedupe_preserve_order(
        requested_stack + suggested_stack
    )


def _bucket_timeline(timeline: str) -> str:
    normalized = timeline.lower().strip()

    if re.search(r"\b(1|one)\s*(week|wk)\b", normalized):
        return "1_week"

    if re.search(r"\b(2|two|3|three)\s*[- ]?\s*(week|weeks|wks)\b", normalized):
        return "2_3_weeks"

    if "month" in normalized or "4 weeks" in normalized:
        return "1_month"

    if "semester" in normalized or "capstone" in normalized:
        return "semester"

    return "2_3_weeks"
