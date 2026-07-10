from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from planning.evidence_cards import build_evidence_cards_from_artifact


VALID_CONFIDENCE_LABELS = {
    "Strong",
    "Limited",
    "Exploratory",
}

EXPECTED_DIRECTION_SCOPES = (
    ("easy", "quick_build", "1-2 days"),
    ("medium", "resume_mvp", "3-5 days"),
    ("hard", "flagship_extension", "1-2 weeks"),
)


@dataclass(frozen=True)
class LLMSynthesisOutputValidation:
    output_path: str
    artifact_path: str | None
    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    cited_source_ids: tuple[str, ...]
    valid_source_ids: tuple[str, ...]
    invented_source_ids: tuple[str, ...]
    direction_grounding_traces: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_saved_synthesis_output(
    *,
    output_path: Path,
    artifact_path: Path | None = None,
) -> LLMSynthesisOutputValidation:
    output = json.loads(output_path.read_text())

    resolved_artifact_path = artifact_path or _artifact_path_from_output(output)
    evidence_card_map = _load_evidence_card_map(resolved_artifact_path)
    valid_source_ids = set(evidence_card_map)

    errors = []
    warnings = []

    response = output.get("response", {})
    parsed_response = response.get("parsed_response")

    if parsed_response is None:
        errors.append("missing_parsed_response")

    response_warnings = response.get("warnings", [])
    if response_warnings:
        errors.append("response_contains_warnings")

    if not output.get("routing_decision"):
        errors.append("missing_routing_decision")

    if not output.get("token_estimate"):
        errors.append("missing_token_estimate")

    if not output.get("provider"):
        errors.append("missing_provider")

    if not output.get("model"):
        errors.append("missing_model")

    cited_source_ids = tuple(sorted(_collect_cited_source_ids(parsed_response)))
    invented_source_ids = tuple(
        source_id
        for source_id in cited_source_ids
        if source_id not in valid_source_ids
    )

    if invented_source_ids:
        errors.append("invented_source_ids")

    if parsed_response is not None:
        _validate_parsed_response(
            parsed_response=parsed_response,
            errors=errors,
            warnings=warnings,
        )

    direction_grounding_traces = _build_direction_grounding_traces(
        parsed_response=parsed_response,
        evidence_card_map=evidence_card_map,
    )

    return LLMSynthesisOutputValidation(
        output_path=str(output_path),
        artifact_path=str(resolved_artifact_path) if resolved_artifact_path else None,
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        cited_source_ids=cited_source_ids,
        valid_source_ids=tuple(sorted(valid_source_ids)),
        invented_source_ids=invented_source_ids,
        direction_grounding_traces=tuple(direction_grounding_traces),
    )


def _artifact_path_from_output(output: dict[str, Any]) -> Path | None:
    artifact_path = output.get("run_metadata", {}).get("artifact_path")
    if not artifact_path:
        return None
    path = Path(artifact_path)
    return path if path.exists() else None


def _load_evidence_card_map(artifact_path: Path | None) -> dict[str, Any]:
    if artifact_path is None:
        return {}

    artifact = json.loads(artifact_path.read_text())
    cards = build_evidence_cards_from_artifact(artifact)

    return {
        card.source_id: card
        for card in cards
    }


def _build_direction_grounding_traces(
    *,
    parsed_response: Any,
    evidence_card_map: dict[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(parsed_response, dict):
        return []

    traces = []
    project_directions = parsed_response.get("project_directions", [])

    for index, direction in enumerate(project_directions):
        if not isinstance(direction, dict):
            traces.append(
                {
                    "direction_index": index,
                    "is_grounded": False,
                    "error": "direction_not_object",
                }
            )
            continue

        cited_source_ids = [
            str(source_id)
            for source_id in direction.get("source_ids", [])
        ]
        valid_cited_source_ids = [
            source_id
            for source_id in cited_source_ids
            if source_id in evidence_card_map
        ]
        invented_source_ids = [
            source_id
            for source_id in cited_source_ids
            if source_id not in evidence_card_map
        ]

        traces.append(
            {
                "direction_index": index,
                "scope_level": direction.get("scope_level"),
                "build_type": direction.get("build_type"),
                "estimated_time": direction.get("estimated_time"),
                "title": direction.get("title"),
                "evidence_confidence": direction.get("evidence_confidence"),
                "is_grounded": bool(cited_source_ids) and not invented_source_ids,
                "cited_source_ids": cited_source_ids,
                "valid_cited_source_ids": valid_cited_source_ids,
                "invented_source_ids": invented_source_ids,
                "grounding_warnings": direction.get("grounding_warnings", []),
                "supporting_evidence_cards": [
                    _evidence_card_trace(evidence_card_map[source_id])
                    for source_id in valid_cited_source_ids
                ],
            }
        )

    return traces


def _evidence_card_trace(card: Any) -> dict[str, Any]:
    return {
        "source_id": card.source_id,
        "source_type": card.source_type,
        "title": card.title,
        "support_scope": card.support_scope,
        "evidence_confidence": card.evidence_confidence,
        "grounding_warning": card.grounding_warning,
    }


def _validate_parsed_response(
    *,
    parsed_response: dict[str, Any],
    errors: list[str],
    warnings: list[str],
) -> None:
    project_directions = parsed_response.get("project_directions")
    if not isinstance(project_directions, list) or not project_directions:
        errors.append("missing_project_directions")
    elif len(project_directions) != len(EXPECTED_DIRECTION_SCOPES):
        errors.append("invalid_project_direction_count")
    else:
        _validate_direction_scope_sequence(
            project_directions=project_directions,
            errors=errors,
        )

    overall_confidence = parsed_response.get("overall_confidence")
    if overall_confidence not in VALID_CONFIDENCE_LABELS:
        errors.append("invalid_overall_confidence")

    for index, direction in enumerate(project_directions or []):
        if not isinstance(direction, dict):
            errors.append(f"project_direction_{index}_not_object")
            continue

        if not direction.get("title"):
            errors.append(f"project_direction_{index}_missing_title")

        if not direction.get("source_ids"):
            errors.append(f"project_direction_{index}_missing_source_ids")

        evidence_confidence = direction.get("evidence_confidence")
        if evidence_confidence not in VALID_CONFIDENCE_LABELS:
            errors.append(
                f"project_direction_{index}_invalid_evidence_confidence"
            )

        if not direction.get("grounding_warnings"):
            warnings.append(
                f"project_direction_{index}_missing_grounding_warnings"
            )

        if not direction.get("resume_bullet"):
            warnings.append(f"project_direction_{index}_missing_resume_bullet")


def _validate_direction_scope_sequence(
    *,
    project_directions: list[Any],
    errors: list[str],
) -> None:
    for index, expected in enumerate(EXPECTED_DIRECTION_SCOPES):
        expected_scope, expected_build_type, expected_time = expected
        direction = project_directions[index]

        if not isinstance(direction, dict):
            continue

        if direction.get("scope_level") != expected_scope:
            errors.append(f"project_direction_{index}_invalid_scope_level")

        if direction.get("build_type") != expected_build_type:
            errors.append(f"project_direction_{index}_invalid_build_type")

        if direction.get("estimated_time") != expected_time:
            errors.append(f"project_direction_{index}_invalid_estimated_time")


def _collect_cited_source_ids(parsed_response: Any) -> set[str]:
    if parsed_response is None:
        return set()

    source_ids = set()
    project_directions = parsed_response.get("project_directions", [])

    for direction in project_directions:
        if not isinstance(direction, dict):
            continue
        for source_id in direction.get("source_ids", []):
            source_ids.add(str(source_id))

    return source_ids


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--artifact-path")
    args = parser.parse_args()

    validation = validate_saved_synthesis_output(
        output_path=Path(args.output_path),
        artifact_path=Path(args.artifact_path) if args.artifact_path else None,
    )

    print(json.dumps(validation.to_dict(), indent=2))

    if not validation.is_valid:
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
