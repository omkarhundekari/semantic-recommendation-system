from typing import Iterable, List

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.planner_models import EvidenceBrief


MIN_MVP_STEPS = 3
MAX_MVP_STEPS = 7
MIN_WORKFLOW_STEPS = 2


def _normalized(value: str) -> str:
    return " ".join(str(value).lower().split())


def _missing_text_fields(candidate: CandidateDirection) -> List[str]:
    fields = {
        "title": candidate.title,
        "problem_statement": candidate.problem_statement,
        "target_user": candidate.target_user,
        "evidence_relationship": candidate.evidence_relationship,
    }

    return [
        field_name
        for field_name, value in fields.items()
        if not _normalized(value)
    ]


def validate_candidate(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
) -> CandidateValidationResult:
    errors = []
    warnings = []

    missing_fields = _missing_text_fields(candidate)

    if missing_fields:
        errors.append(
            "Missing required text fields: "
            + ", ".join(missing_fields)
            + "."
        )

    if len(candidate.core_workflow) < MIN_WORKFLOW_STEPS:
        errors.append(
            f"Core workflow needs at least {MIN_WORKFLOW_STEPS} steps."
        )

    if not MIN_MVP_STEPS <= len(candidate.mvp_scope) <= MAX_MVP_STEPS:
        errors.append(
            f"MVP scope must contain {MIN_MVP_STEPS}-{MAX_MVP_STEPS} steps."
        )

    known_source_ids = {
        source.source_id
        for source in brief.sources
    }

    unknown_source_ids = [
        source_id
        for source_id in candidate.source_ids
        if source_id not in known_source_ids
    ]

    if unknown_source_ids:
        errors.append(
            "Candidate references source IDs outside the evidence brief: "
            + ", ".join(unknown_source_ids)
            + "."
        )

    if not candidate.source_ids:
        warnings.append(
            "Candidate has no named source IDs and should use planning-domain support."
        )

    if len(set(_normalized(step) for step in candidate.mvp_scope)) != len(
        candidate.mvp_scope
    ):
        errors.append("MVP scope contains duplicate steps.")

    return CandidateValidationResult(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def validate_candidate_set(
    candidates: Iterable[CandidateDirection],
    brief: EvidenceBrief,
) -> List[CandidateValidationResult]:
    candidate_list = list(candidates)
    results = [
        validate_candidate(candidate, brief)
        for candidate in candidate_list
    ]

    seen_titles = set()

    for index, candidate in enumerate(candidate_list):
        normalized_title = _normalized(candidate.title)

        if normalized_title and normalized_title in seen_titles:
            results[index].errors.append(
                "Candidate title duplicates another direction."
            )
            results[index].is_valid = False

        seen_titles.add(normalized_title)

    return results
