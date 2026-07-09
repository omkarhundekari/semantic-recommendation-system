from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from planning.evidence_cards import build_evidence_cards_from_artifact
from planning.llm_routing_policy import (
    DEEP_MODE,
    FAST_MODE,
    INTERVIEW_MODE,
    LLMRoutingDecision,
    SessionBudgetState,
    decide_llm_routing,
)
from planning.token_estimation import (
    TokenEstimate,
    estimate_llm_synthesis_prompt_tokens,
)


DEFAULT_SYNTHESIS_SYSTEM_INSTRUCTION = (
    "Generate grounded project directions using only the provided evidence cards. "
    "Cite only source IDs that appear in the evidence cards. Preserve grounding "
    "warnings and avoid overconfident claims when evidence is limited or adjacent."
)

DEFAULT_SYNTHESIS_OUTPUT_SCHEMA = {
    "candidates": [
        {
            "title": "string",
            "problem_statement": "string",
            "target_user": "string",
            "source_ids": ["string"],
            "evidence_confidence": "Strong | Limited | Exploratory",
            "grounding_notes": ["string"],
            "mvp_scope": ["string"],
            "advanced_extensions": ["string"],
            "skills_demonstrated": ["string"],
            "resume_bullet": "string",
            "interview_talking_points": ["string"],
        }
    ],
    "overall_confidence": "Strong | Limited | Exploratory",
    "assumptions": ["string"],
    "warnings": ["string"],
}


@dataclass(frozen=True)
class ModeLLMReadiness:
    mode: str
    routing_decision: LLMRoutingDecision
    token_estimate: TokenEstimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "routing_decision": self.routing_decision.to_dict(),
            "token_estimate": self.token_estimate.to_dict(),
        }


@dataclass(frozen=True)
class LLMReadinessReport:
    artifact_id: str
    fixture_id: str
    evidence_card_count: int
    evidence_confidence_counts: dict[str, int]
    grounding_warning_counts: dict[str, int]
    relevance_signal_counts: dict[str, int]
    mode_reports: tuple[ModeLLMReadiness, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "fixture_id": self.fixture_id,
            "evidence_card_count": self.evidence_card_count,
            "evidence_confidence_counts": self.evidence_confidence_counts,
            "grounding_warning_counts": self.grounding_warning_counts,
            "relevance_signal_counts": self.relevance_signal_counts,
            "mode_reports": [
                mode_report.to_dict()
                for mode_report in self.mode_reports
            ],
        }


def build_llm_readiness_report_from_artifact(
    artifact: dict[str, Any],
    *,
    session_budget: SessionBudgetState,
    modes: tuple[str, ...] = (FAST_MODE, DEEP_MODE, INTERVIEW_MODE),
    system_instruction: str = DEFAULT_SYNTHESIS_SYSTEM_INSTRUCTION,
    output_schema: dict[str, Any] | None = None,
) -> LLMReadinessReport:
    output_schema = output_schema or DEFAULT_SYNTHESIS_OUTPUT_SCHEMA
    evidence_cards = build_evidence_cards_from_artifact(artifact)

    mode_reports = []
    for mode in modes:
        token_estimate = estimate_llm_synthesis_prompt_tokens(
            user_goal=artifact["query"],
            constraints=artifact["constraints"],
            evidence_cards=evidence_cards,
            mode=mode,
            system_instruction=system_instruction,
            output_schema=output_schema,
        )
        routing_decision = decide_llm_routing(
            evidence_cards=evidence_cards,
            session_budget=session_budget,
            mode=mode,
            estimated_tokens=token_estimate.estimated_tokens,
        )
        mode_reports.append(
            ModeLLMReadiness(
                mode=mode,
                routing_decision=routing_decision,
                token_estimate=token_estimate,
            )
        )

    return LLMReadinessReport(
        artifact_id=artifact["artifact_identity"]["artifact_id"],
        fixture_id=artifact["artifact_identity"]["fixture_id"],
        evidence_card_count=len(evidence_cards),
        evidence_confidence_counts=_count_card_field(
            evidence_cards,
            "evidence_confidence",
        ),
        grounding_warning_counts=_count_card_field(
            evidence_cards,
            "grounding_warning",
        ),
        relevance_signal_counts=_count_card_field(
            evidence_cards,
            "relevance_signal",
        ),
        mode_reports=tuple(mode_reports),
    )


def render_llm_readiness_report_markdown(
    report: LLMReadinessReport,
) -> str:
    lines = [
        f"# LLM Readiness Report: {report.fixture_id}",
        "",
        f"- Artifact: `{report.artifact_id}`",
        f"- Evidence cards: {report.evidence_card_count}",
        "",
        "## Evidence Card Summary",
        "",
        "Evidence confidence:",
    ]

    lines.extend(_render_counts(report.evidence_confidence_counts))
    lines.extend(["", "Grounding warnings:"])
    lines.extend(_render_counts(report.grounding_warning_counts))
    lines.extend(["", "Relevance signals:"])
    lines.extend(_render_counts(report.relevance_signal_counts))

    lines.extend(["", "## Mode Routing Summary"])

    for mode_report in report.mode_reports:
        decision = mode_report.routing_decision
        estimate = mode_report.token_estimate
        lines.extend(
            [
                "",
                f"### {mode_report.mode}",
                f"- Should route: `{decision.should_route}`",
                f"- Reason: `{decision.reason}`",
                f"- Evidence confidence: `{decision.evidence_confidence}`",
                f"- Query-aligned cards: {decision.query_aligned_card_count}",
                f"- Weak cards: {decision.weak_card_count}",
                f"- Suspicious cards: {decision.suspicious_card_count}",
                f"- Estimated prompt tokens: {estimate.estimated_tokens}",
                (
                    "- Largest sections: "
                    + ", ".join(f"`{section}`" for section in estimate.largest_sections)
                ),
            ]
        )

    return "\n".join(lines) + "\n"


def write_llm_readiness_report(
    report: LLMReadinessReport,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{report.fixture_id}_{report.artifact_id}_llm_readiness"
    json_path = output_dir / f"{base_name}.json"
    markdown_path = output_dir / f"{base_name}.md"

    json_path.write_text(json.dumps(report.to_dict(), indent=2))
    markdown_path.write_text(render_llm_readiness_report_markdown(report))

    return {
        "json_path": json_path,
        "markdown_path": markdown_path,
    }


def _count_card_field(
    cards: list[Any],
    field_name: str,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        value = getattr(card, field_name)
        if value is None:
            value = "none"
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


def _render_counts(counts: dict[str, int]) -> list[str]:
    if not counts:
        return ["- none"]
    return [
        f"- `{name}`: {count}"
        for name, count in sorted(counts.items())
    ]


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-path", required=True)
    parser.add_argument("--output-dir", default="outputs/reports/llm_readiness")
    parser.add_argument("--calls-remaining", type=int, default=5)
    parser.add_argument("--tokens-remaining", type=int, default=10000)
    args = parser.parse_args()

    artifact = json.loads(Path(args.artifact_path).read_text())
    report = build_llm_readiness_report_from_artifact(
        artifact,
        session_budget=SessionBudgetState(
            calls_remaining=args.calls_remaining,
            tokens_remaining=args.tokens_remaining,
            budget_available=True,
        ),
    )
    paths = write_llm_readiness_report(report, Path(args.output_dir))

    print(f"Wrote Markdown report: {paths['markdown_path']}")
    print(f"Wrote JSON report: {paths['json_path']}")


if __name__ == "__main__":
    _main()
