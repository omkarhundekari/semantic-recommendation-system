from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


LOW_GOAL_ALIGNMENT_THRESHOLD = 0.45
WEAK_GROUNDING_ALIGNMENT_THRESHOLD = 0.20
NEAR_DUPLICATE_WARNING_THRESHOLD = 0.78


@dataclass(frozen=True)
class ShadowQualityWarning:
    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ShadowQualityWarningAssessment:
    warnings: List[ShadowQualityWarning]
    signals: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "warnings": [
                warning.to_dict()
                for warning in self.warnings
            ],
            "signals": dict(self.signals),
        }


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def assess_shadow_quality_warnings(
    coverage_warnings: Sequence[str],
    semantic_goal_relevance: Sequence[Dict[str, Any]],
    grounding_adequacy: Sequence[Dict[str, Any]],
    semantic_candidate_diversity: Optional[Dict[str, Any]] = None,
    candidate_source_relevance: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
) -> ShadowQualityWarningAssessment:
    warnings: List[ShadowQualityWarning] = []
    coverage = list(coverage_warnings)

    if any(
        "No research-paper evidence" in warning
        for warning in coverage
    ):
        warnings.append(
            ShadowQualityWarning(
                code="missing_direct_research_evidence",
                message=(
                    "The evidence brief has no research-paper evidence, "
                    "so research grounding should be reviewed manually."
                ),
            )
        )

    low_goal_candidates = []

    for trace in semantic_goal_relevance:
        score = _float_or_none(trace.get("raw_cosine"))

        if (
            score is not None
            and score < LOW_GOAL_ALIGNMENT_THRESHOLD
        ):
            low_goal_candidates.append(
                {
                    "candidate_title": trace.get("candidate_title", ""),
                    "raw_cosine": round(score, 4),
                }
            )

    if low_goal_candidates:
        warnings.append(
            ShadowQualityWarning(
                code="low_goal_alignment",
                message=(
                    "One or more candidates have low semantic alignment "
                    "with the requested project goal."
                ),
                details={
                    "threshold": LOW_GOAL_ALIGNMENT_THRESHOLD,
                    "candidates": low_goal_candidates,
                },
            )
        )

    weak_grounding_candidates = []

    for trace in grounding_adequacy:
        score = _float_or_none(
            trace.get("min_cited_alignment")
        )

        if (
            score is not None
            and score < WEAK_GROUNDING_ALIGNMENT_THRESHOLD
        ):
            weak_grounding_candidates.append(
                {
                    "candidate_title": trace.get("candidate_title", ""),
                    "min_cited_alignment": round(score, 4),
                }
            )

    if weak_grounding_candidates:
        warnings.append(
            ShadowQualityWarning(
                code="weak_grounding_alignment",
                message=(
                    "One or more candidates cite valid evidence but have "
                    "weak candidate-to-source semantic alignment."
                ),
                details={
                    "threshold": WEAK_GROUNDING_ALIGNMENT_THRESHOLD,
                    "candidates": weak_grounding_candidates,
                },
            )
        )

    diversity_pairs = (
        semantic_candidate_diversity.get(
            "pairwise_similarity",
            [],
        )
        if semantic_candidate_diversity
        else []
    )

    close_pairs = []

    for pair in diversity_pairs:
        score = _float_or_none(pair.get("raw_cosine"))

        if (
            score is not None
            and score >= NEAR_DUPLICATE_WARNING_THRESHOLD
        ):
            close_pairs.append(
                {
                    "candidate_a_title": pair.get(
                        "candidate_a_title",
                        "",
                    ),
                    "candidate_b_title": pair.get(
                        "candidate_b_title",
                        "",
                    ),
                    "raw_cosine": round(score, 4),
                }
            )

    if close_pairs:
        warnings.append(
            ShadowQualityWarning(
                code="near_duplicate_candidates",
                message=(
                    "One or more candidate pairs are semantically close "
                    "and should be reviewed for meaningful distinction."
                ),
                details={
                    "threshold": NEAR_DUPLICATE_WARNING_THRESHOLD,
                    "pairs": close_pairs,
                },
            )
        )

    source_relevance_traces = list(candidate_source_relevance or [])
    traces_by_candidate: Dict[str, List[Dict[str, Any]]] = {}

    for trace in source_relevance_traces:
        candidate_title = trace.get("candidate_title", "")

        if candidate_title:
            traces_by_candidate.setdefault(
                candidate_title,
                [],
            ).append(trace)

    adjacent_only_candidates = []

    for candidate_title, traces in traces_by_candidate.items():
        statuses = {
            trace.get("relevance_status")
            for trace in traces
        }

        if statuses == {"adjacent_context_only"}:
            adjacent_only_candidates.append(
                {
                    "candidate_title": candidate_title,
                    "source_ids": [
                        trace.get("source_id", "")
                        for trace in traces
                    ],
                    "relevance_statuses": sorted(statuses),
                }
            )

    if adjacent_only_candidates:
        warnings.append(
            ShadowQualityWarning(
                code="adjacent_context_only_candidate",
                message=(
                    "One or more candidates cite only adjacent-context "
                    "sources and should not be treated as strongly grounded."
                ),
                details={
                    "candidates": adjacent_only_candidates,
                },
            )
        )

    return ShadowQualityWarningAssessment(
        warnings=warnings,
        signals={
            "coverage_warning_count": len(coverage),
            "goal_trace_count": len(semantic_goal_relevance),
            "grounding_trace_count": len(grounding_adequacy),
            "diversity_pair_count": len(diversity_pairs),
            "source_relevance_trace_count": len(source_relevance_traces),
            "quality_warning_count": len(warnings),
        },
    )
