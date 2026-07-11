from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from planning.domain_playbook_loader import DomainPlaybook, load_playbook_or_generic
from planning.query_anchor_direction_adapter import extract_query_anchors


@dataclass(frozen=True)
class MissionContext:
    user_goal: str
    project_title: str
    project_summary: str
    resolved_planning_domain: str
    query_anchors: List[str]
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


def build_mission_context(
    *,
    idea: Dict[str, Any],
    user_goal: str,
    resolved_planning_domain: Optional[str],
    query: str,
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
    idea_stack = _as_string_list(idea.get("suggested_tech_stack"))
    primary_stack = _dedupe_preserve_order(preferred_stack + idea_stack)[:5]

    query_anchors = extract_query_anchors(query or user_goal)
    if not query_anchors:
        query_anchors = extract_query_anchors(
            " ".join(
                [
                    str(idea.get("project_title", "") or ""),
                    str(idea.get("project_summary", "") or ""),
                ]
            )
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
        query_anchors=query_anchors[:4],
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
