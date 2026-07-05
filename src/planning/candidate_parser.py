import json
from typing import Any, Dict, List

from planning.candidate_models import CandidateDirection


REQUIRED_CANDIDATE_FIELDS = {
    "title",
    "problem_statement",
    "target_user",
    "core_workflow",
    "mvp_scope",
    "success_metrics",
    "evidence_relationship",
}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return [str(value).strip()] if str(value).strip() else []


def _parse_json_object(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Provider response is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Provider response must be a JSON object.")

    return payload


def _parse_candidate_object(
    raw_candidate: Any,
    label: str,
) -> CandidateDirection:
    if not isinstance(raw_candidate, dict):
        raise ValueError(f"{label} must be a JSON object.")

    missing = sorted(
        field
        for field in REQUIRED_CANDIDATE_FIELDS
        if field not in raw_candidate
    )

    if missing:
        raise ValueError(
            f"{label} is missing required fields: "
            + ", ".join(missing)
            + "."
        )

    return CandidateDirection(
        title=str(raw_candidate["title"]).strip(),
        problem_statement=str(
            raw_candidate["problem_statement"]
        ).strip(),
        target_user=str(raw_candidate["target_user"]).strip(),
        core_workflow=_as_list(raw_candidate["core_workflow"]),
        mvp_scope=_as_list(raw_candidate["mvp_scope"]),
        success_metrics=_as_list(raw_candidate["success_metrics"]),
        evidence_relationship=str(
            raw_candidate["evidence_relationship"]
        ).strip(),
        source_ids=_as_list(raw_candidate.get("source_ids")),
        assumptions=_as_list(raw_candidate.get("assumptions")),
        suggested_stack=_as_list(raw_candidate.get("suggested_stack")),
    )


def parse_candidate_payload(payload: Any) -> List[CandidateDirection]:
    payload = _parse_json_object(payload)
    raw_candidates = payload.get("candidates")

    if not isinstance(raw_candidates, list):
        raise ValueError("Provider response must contain a candidates list.")

    return [
        _parse_candidate_object(
            raw_candidate,
            f"Candidate {index}",
        )
        for index, raw_candidate in enumerate(raw_candidates, start=1)
    ]


def parse_single_candidate_payload(payload: Any) -> CandidateDirection:
    payload = _parse_json_object(payload)
    raw_candidate = payload.get("candidate")

    if raw_candidate is None:
        raise ValueError(
            "Regeneration response must contain a candidate object."
        )

    return _parse_candidate_object(
        raw_candidate,
        "Regenerated candidate",
    )
