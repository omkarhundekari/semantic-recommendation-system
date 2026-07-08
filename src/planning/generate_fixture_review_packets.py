import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from planning.manual_review_rubric import ManualReviewRubric
from planning.mock_generation_provider import MockCandidateGenerationProvider
from planning.shadow_comparison_demo import build_shadow_comparison_artifact
from planning.shadow_fixture_specs import (
    ShadowFixtureSpecification,
    fixture_specifications,
)


DEFAULT_OUTPUT_DIR = Path("outputs/manual_fixture_reviews")


def available_fixture_ids() -> Tuple[str, ...]:
    return tuple(
        specification.case.case_id
        for specification in fixture_specifications()
    )


def select_fixture_specifications(
    fixture_ids: Optional[Sequence[str]] = None,
) -> Tuple[ShadowFixtureSpecification, ...]:
    specifications = fixture_specifications()

    if fixture_ids is None:
        return specifications

    requested = {
        str(fixture_id).strip()
        for fixture_id in fixture_ids
        if str(fixture_id).strip()
    }

    selected = tuple(
        specification
        for specification in specifications
        if specification.case.case_id in requested
    )

    missing = requested.difference(
        specification.case.case_id
        for specification in selected
    )

    if missing:
        raise ValueError(
            "Unknown fixture specification IDs: "
            + ", ".join(sorted(missing))
        )

    return selected


def build_fixture_artifact(
    specification: ShadowFixtureSpecification,
) -> Dict[str, Any]:
    specification.validate()

    return build_shadow_comparison_artifact(
        evidence_payload=specification.evidence_payload,
        user_goal=specification.case.user_goal,
        constraints=specification.case.constraints,
        provider=MockCandidateGenerationProvider(
            response=specification.mock_response
        ),
        fixture_id=specification.case.case_id,
    )


def render_review_packet(
    artifact: Dict[str, Any],
    specification: ShadowFixtureSpecification,
    rubric: Optional[ManualReviewRubric] = None,
) -> str:
    rubric = rubric or ManualReviewRubric()

    shadow = artifact["v2_shadow"]
    report = shadow["report"]
    brief = report["evidence_brief"]
    quality = shadow["evidence_quality"]
    quality_warnings = shadow.get("quality_warnings", {})
    comparison = shadow["shadow_vs_deterministic_comparison"]
    source_relevance = shadow.get("candidate_source_relevance", [])
    template = shadow["manual_review_template"]

    brief_sources = {
        source["source_id"]: source
        for source in brief["sources"]
    }

    lines: List[str] = [
        f"# Manual Review Packet: {specification.case.case_id}",
        "",
        "## Artifact Identity",
        "```json",
        json.dumps(artifact["artifact_identity"], indent=2),
        "```",
        "",
        "## User Goal",
        artifact["query"],
        "",
        "## Constraints",
        "```json",
        json.dumps(artifact["constraints"], indent=2),
        "```",
        "",
        "## Reviewer Focus",
        specification.case.reviewer_focus,
        "",
        "## Rubric",
        f"- Goal alignment: {rubric.goal_alignment_instruction}",
        f"- Grounding: {rubric.grounding_instruction}",
        f"- Scope realism: {rubric.scope_realism_instruction}",
        f"- Distinctiveness: {rubric.distinctiveness_instruction}",
        "- Overall preference options: deterministic, openai, tie, both_weak.",
        "- Response quality options: standard, limited, exploratory.",
        "",
        "## Evidence Brief",
    ]

    for source in brief["sources"]:
        lines.extend(
            [
                f"### {source['source_id']} — {source['title']}",
                f"- Type: {source['source_type']}",
                f"- Support scope: {source['support_scope']}",
                f"- Excerpt: {source['excerpt']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Evidence Quality Diagnostics",
            "```json",
            json.dumps(quality, indent=2),
            "```",
            "",
            "## Deterministic Directions: Raw Inputs",
        ]
    )

    for idea in artifact["legacy_planner"]["raw_ideas"]:
        lines.extend(
            [
                f"### {idea.get('project_title', 'Untitled')}",
                (
                    "- Problem / angle: "
                    f"{idea.get('idea_angle', '')}"
                ),
                f"- Evidence title: {idea.get('evidence_title', '')}",
                (
                    "- Evidence type: "
                    f"{idea.get('evidence_source_type', '')}"
                ),
                "- MVP scope:",
            ]
        )
        lines.extend(
            f"  - {step}"
            for step in idea.get("mvp_scope", [])
        )

    lines.extend(["", "## Shadow Directions: Raw Candidates"])

    for candidate in shadow["raw_candidates"]:
        source_ids = candidate.get("source_ids", [])

        lines.extend(
            [
                f"### {candidate.get('title', 'Untitled')}",
                f"- Problem: {candidate.get('problem_statement', '')}",
                f"- Target user: {candidate.get('target_user', '')}",
                (
                    "- Evidence relationship: "
                    f"{candidate.get('evidence_relationship', '')}"
                ),
                f"- Source IDs: {source_ids}",
                "- Cited evidence:",
            ]
        )

        for source_id in source_ids:
            source = brief_sources.get(source_id)

            if source is None:
                lines.append(f"  - {source_id}: missing from brief")
            else:
                lines.append(
                    f"  - {source_id}: {source['title']} "
                    f"({source['support_scope']})"
                )

        lines.append("- MVP scope:")
        lines.extend(
            f"  - {step}"
            for step in candidate.get("mvp_scope", [])
        )

    lines.extend(
        [
            "",
            "## Candidate-to-Source Relevance Diagnostics",
            "```json",
            json.dumps(source_relevance, indent=2),
            "```",
            "",
            "## Quality Warnings",
            "```json",
            json.dumps(quality_warnings, indent=2),
            "```",
        ]
    )

    semantic_status = (
        "assessed"
        if comparison.get("set_similarity_score") is not None
        else "not_assessed_no_comparison_encoder"
    )

    lines.extend(
        [
            "",
            "## Comparison Diagnostics",
            "```json",
            json.dumps(
                {
                    "semantic_comparison_status": semantic_status,
                    "set_similarity_score": comparison.get(
                        "set_similarity_score"
                    ),
                    "unique_angle_count": (
                        comparison.get("unique_angle_count")
                        if semantic_status == "assessed"
                        else None
                    ),
                    "unique_openai_titles": (
                        comparison.get("unique_openai_titles")
                        if semantic_status == "assessed"
                        else []
                    ),
                    "notes": comparison.get("notes"),
                },
                indent=2,
            ),
            "```",
            "",
            "## Unscored Manual Review Template",
            "```json",
            json.dumps(template, indent=2),
            "```",
        ]
    )

    return "\n".join(lines) + "\n"


def write_fixture_review_packets(
    specifications: Iterable[ShadowFixtureSpecification],
    output_dir: Path,
) -> List[Dict[str, Path]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: List[Dict[str, Path]] = []

    for specification in specifications:
        artifact = build_fixture_artifact(specification)
        case_id = specification.case.case_id
        artifact_id = artifact["artifact_identity"]["artifact_id"]

        fixture_output_dir = output_dir / case_id
        fixture_output_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = fixture_output_dir / f"{artifact_id}.json"
        packet_path = fixture_output_dir / f"{artifact_id}_review.md"

        artifact_path.write_text(json.dumps(artifact, indent=2))
        packet_path.write_text(
            render_review_packet(
                artifact=artifact,
                specification=specification,
            )
        )

        written.append(
            {
                "artifact_path": artifact_path,
                "packet_path": packet_path,
            }
        )

    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate local mock-based shadow fixture artifacts and "
            "self-contained manual-review packets."
        )
    )
    parser.add_argument(
        "--fixture-id",
        action="append",
        dest="fixture_ids",
        choices=available_fixture_ids(),
        help=(
            "Fixture specification ID to generate. Repeat for multiple "
            "fixtures. Omit to generate all available specifications."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for generated JSON artifacts and Markdown packets.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    specifications = select_fixture_specifications(args.fixture_ids)
    written = write_fixture_review_packets(
        specifications=specifications,
        output_dir=Path(args.output_dir),
    )

    for paths in written:
        print(f"Wrote artifact: {paths['artifact_path']}")
        print(f"Wrote review packet: {paths['packet_path']}")


if __name__ == "__main__":
    main()
