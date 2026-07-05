import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
    build_semantic_diversification_repair_plan,
)


@dataclass(frozen=True)
class RegenerationSourceArtifact:
    path: Path
    brief: EvidenceBrief
    request: CandidateGenerationRequest
    directive: DiversificationRepairDirective
    retained_candidates: List[CandidateDirection]
    surviving_candidates: List[CandidateDirection]
    replaced_candidate: CandidateDirection


def _candidate_from_payload(payload: Dict[str, Any]) -> CandidateDirection:
    return CandidateDirection(
        **{
            key: value
            for key, value in payload.items()
            if key != "ranking"
        }
    )


def _brief_from_payload(payload: Dict[str, Any]) -> EvidenceBrief:
    sources = [
        EvidenceSource(
            source_id=str(source.get("source_id", "")),
            source_type=str(source.get("source_type", "unknown")),
            title=str(source.get("title", "")),
            excerpt=str(source.get("excerpt", "")),
            category=source.get("category"),
            url=source.get("url"),
            retrieval_rank=source.get("retrieval_rank"),
            retrieval_signals=dict(
                source.get("retrieval_signals", {})
            ),
            support_scope=str(source.get("support_scope", "direct")),
            retention_reason=str(
                source.get("retention_reason", "")
            ),
        )
        for source in payload.get("sources", [])
        if isinstance(source, dict)
    ]

    if not sources:
        raise ValueError(
            "Source artifact does not contain an evidence brief with sources."
        )

    return EvidenceBrief(
        query=str(payload.get("query", "")),
        sources=sources,
        source_counts=dict(payload.get("source_counts", {})),
        recurring_concepts=list(
            payload.get("recurring_concepts", [])
        ),
        coverage_warnings=list(
            payload.get("coverage_warnings", [])
        ),
    )


def _repair_plan_from_shadow(shadow: Dict[str, Any]) -> Dict[str, Any]:
    existing = shadow.get("semantic_diversification_repair")

    if isinstance(existing, dict) and existing.get("directives"):
        return existing

    selected_candidates = shadow.get("selected_candidates", [])
    diversity = shadow.get("semantic_candidate_diversity")

    if not selected_candidates or not isinstance(diversity, dict):
        raise ValueError(
            "Source artifact lacks selected candidates or semantic "
            "diversity traces needed to build a repair plan."
        )

    return build_semantic_diversification_repair_plan(
        selected_candidates=selected_candidates,
        semantic_candidate_diversity=diversity,
    ).to_dict()


def load_regeneration_source_artifact(
    path: Path,
    directive_index: int = 0,
) -> RegenerationSourceArtifact:
    if not path.exists():
        raise ValueError(f"Source artifact was not found: {path}")

    try:
        artifact = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Source artifact is not valid JSON."
        ) from exc

    shadow = artifact.get("v2_shadow")

    if not isinstance(shadow, dict):
        raise ValueError("Source artifact does not contain v2_shadow.")

    report = shadow.get("report", {})
    brief_payload = report.get(
        "evidence_brief",
        shadow.get("evidence_brief", {}),
    )

    if not isinstance(brief_payload, dict):
        raise ValueError(
            "Source artifact does not contain an evidence brief."
        )

    brief = _brief_from_payload(brief_payload)

    candidate_payloads = shadow.get("selected_candidates", [])

    if not isinstance(candidate_payloads, list) or not candidate_payloads:
        raise ValueError(
            "Source artifact does not contain selected candidates."
        )

    try:
        candidates = [
            _candidate_from_payload(candidate)
            for candidate in candidate_payloads
            if isinstance(candidate, dict)
        ]
    except TypeError as exc:
        raise ValueError(
            "Source artifact contains an invalid selected candidate."
        ) from exc

    candidates_by_title = {
        candidate.title: candidate
        for candidate in candidates
    }

    repair_plan = _repair_plan_from_shadow(shadow)
    directives = repair_plan.get("directives", [])

    if not directives:
        raise ValueError(
            "Source artifact has no diversification repair directive."
        )

    if directive_index < 0 or directive_index >= len(directives):
        raise ValueError(
            "directive_index is outside the available repair directives."
        )

    directive_payload = directives[directive_index]

    directive = DiversificationRepairDirective(
        replace_candidate_title=str(
            directive_payload.get("replace_candidate_title", "")
        ),
        retain_candidate_titles=list(
            directive_payload.get("retain_candidate_titles", [])
        ),
        highest_pair_similarity=float(
            directive_payload.get("highest_pair_similarity", 0.0)
        ),
        reason=str(directive_payload.get("reason", "")),
        regeneration_brief=dict(
            directive_payload.get("regeneration_brief", {})
        ),
        replacement_angle=str(
            directive_payload.get("replacement_angle", "")
        ).strip(),
    )

    replaced_candidate = candidates_by_title.get(
        directive.replace_candidate_title
    )

    if replaced_candidate is None:
        raise ValueError(
            "Repair directive replacement title is not a selected candidate."
        )

    retained_candidates = [
        candidates_by_title[title]
        for title in directive.retain_candidate_titles
        if title in candidates_by_title
    ]

    if not retained_candidates:
        raise ValueError(
            "Repair directive does not resolve to retained candidates."
        )

    surviving_candidates = [
        candidate
        for candidate in candidates
        if candidate.title != directive.replace_candidate_title
    ]

    if not surviving_candidates:
        raise ValueError(
            "Source artifact has no surviving candidates for replacement "
            "comparison."
        )

    constraints = artifact.get("constraints", {})
    user_goal = str(artifact.get("query") or brief.query).strip()

    if not user_goal:
        raise ValueError("Source artifact does not contain a user goal.")

    request = CandidateGenerationRequest(
        user_goal=user_goal,
        skill_level=str(constraints.get("skill_level") or ""),
        time_available=str(constraints.get("time_available") or ""),
        target_roles=list(constraints.get("target_roles") or []),
        preferred_stack=list(constraints.get("preferred_stack") or []),
    )

    return RegenerationSourceArtifact(
        path=path,
        brief=brief,
        request=request,
        directive=directive,
        retained_candidates=retained_candidates,
        surviving_candidates=surviving_candidates,
        replaced_candidate=replaced_candidate,
    )
