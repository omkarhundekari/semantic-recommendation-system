from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from planning.evidence_curation import EvidenceCurationResult
from planning.planner_models import EvidenceBrief


CALIBRATION_STATUSES = {
    "unresolved",
    "calibrated",
}


@dataclass(frozen=True)
class EvidenceQualityMetrics:
    """
    Observable evidence facts from the current pipeline.

    Curation-stage metrics describe lexical/anchor coverage before the brief.
    Final-brief metrics describe the evidence actually available to planning.
    """

    curation_pool_size: int
    retained_source_count: int
    final_brief_source_count: int

    direct_source_count: int
    adjacent_source_count: int

    required_anchor_count: int
    matched_required_anchor_count: int
    query_anchor_coverage: Optional[float]

    unique_query_term_count: int
    unique_query_phrase_count: int

    source_type_count: int
    dominant_source_type: Optional[str]
    dominant_source_type_fraction: Optional[float]

    top_direct_relevance_margin: Optional[float]
    coverage_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceQualityThresholds:
    """
    Calibration-dependent thresholds.

    No threshold may be guessed. `calibrated` requires all three routing
    thresholds to be supplied from measured artifact-history distributions.
    """

    version: str = "v1"
    calibration_status: str = "unresolved"

    sparse_direct_source_threshold: Optional[int] = None
    ambiguity_top_margin_threshold: Optional[float] = None
    low_diversity_fraction_threshold: Optional[float] = None

    def validate(self) -> None:
        if self.calibration_status not in CALIBRATION_STATUSES:
            raise ValueError(
                "calibration_status must be 'unresolved' or 'calibrated'."
            )

        threshold_values = {
            "sparse_direct_source_threshold": (
                self.sparse_direct_source_threshold
            ),
            "ambiguity_top_margin_threshold": (
                self.ambiguity_top_margin_threshold
            ),
            "low_diversity_fraction_threshold": (
                self.low_diversity_fraction_threshold
            ),
        }

        if self.calibration_status == "unresolved":
            if any(value is not None for value in threshold_values.values()):
                raise ValueError(
                    "Unresolved calibration cannot contain routing thresholds."
                )
            return

        if any(value is None for value in threshold_values.values()):
            raise ValueError(
                "Calibrated thresholds require all routing threshold values."
            )

        if self.sparse_direct_source_threshold < 0:
            raise ValueError(
                "sparse_direct_source_threshold cannot be negative."
            )

        if self.ambiguity_top_margin_threshold < 0:
            raise ValueError(
                "ambiguity_top_margin_threshold cannot be negative."
            )

        if not 0.0 <= self.low_diversity_fraction_threshold <= 1.0:
            raise ValueError(
                "low_diversity_fraction_threshold must be between 0 and 1."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass(frozen=True)
class EvidenceQualitySignals:
    """
    Routing-ready booleans only when calibration and required metrics exist.

    `None` never means False. It means the signal has not been honestly
    resolved yet, so routing must not consume this object.
    """

    metrics: EvidenceQualityMetrics
    thresholds: EvidenceQualityThresholds

    evidence_sparse: Optional[bool]
    evidence_ambiguous: Optional[bool]
    source_diversity_low: Optional[bool]

    unresolved_signal_names: List[str] = field(default_factory=list)

    @property
    def routing_ready(self) -> bool:
        return not self.unresolved_signal_names

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "thresholds": self.thresholds.to_dict(),
            "evidence_sparse": self.evidence_sparse,
            "evidence_ambiguous": self.evidence_ambiguous,
            "source_diversity_low": self.source_diversity_low,
            "unresolved_signal_names": list(
                self.unresolved_signal_names
            ),
            "routing_ready": self.routing_ready,
        }


def _source_type(value: Any) -> str:
    return str(value or "unknown").strip() or "unknown"


def build_evidence_quality_metrics(
    curation: EvidenceCurationResult,
    brief: EvidenceBrief,
) -> EvidenceQualityMetrics:
    retained = list(curation.retained)
    direct_entries = [
        entry
        for entry in retained
        if entry.support_scope == "direct"
    ]

    required_anchors = {
        str(anchor).strip().lower()
        for anchor in curation.required_anchor_terms
        if str(anchor).strip()
    }
    matched_anchors = {
        str(anchor).strip().lower()
        for entry in retained
        for anchor in entry.matched_anchor_terms
        if str(anchor).strip()
    }

    unique_query_terms = {
        str(term).strip().lower()
        for entry in retained
        for term in entry.unique_query_terms
        if str(term).strip()
    }
    unique_query_phrases = {
        str(phrase).strip().lower()
        for entry in retained
        for phrase in entry.unique_query_phrases
        if str(phrase).strip()
    }

    brief_source_types = [
        _source_type(source.source_type)
        for source in brief.sources
    ]
    source_type_counts: Dict[str, int] = {}

    for source_type in brief_source_types:
        source_type_counts[source_type] = (
            source_type_counts.get(source_type, 0) + 1
        )

    dominant_source_type = None
    dominant_source_type_fraction = None

    if source_type_counts and brief.sources:
        dominant_source_type = sorted(
            source_type_counts,
            key=lambda source_type: (
                -source_type_counts[source_type],
                source_type,
            ),
        )[0]
        dominant_source_type_fraction = (
            source_type_counts[dominant_source_type]
            / len(brief.sources)
        )

    direct_scores = sorted(
        (
            float(entry.relevance_score)
            for entry in direct_entries
        ),
        reverse=True,
    )
    top_direct_relevance_margin = None

    if len(direct_scores) >= 2:
        top_direct_relevance_margin = round(
            direct_scores[0] - direct_scores[1],
            6,
        )

    curation_pool_size = max(
        [entry.curation_pool_size for entry in retained] or [0]
    )

    return EvidenceQualityMetrics(
        curation_pool_size=curation_pool_size,
        retained_source_count=len(retained),
        final_brief_source_count=len(brief.sources),
        direct_source_count=sum(
            source.support_scope == "direct"
            for source in brief.sources
        ),
        adjacent_source_count=sum(
            source.support_scope == "adjacent_planning"
            for source in brief.sources
        ),
        required_anchor_count=len(required_anchors),
        matched_required_anchor_count=len(
            required_anchors.intersection(matched_anchors)
        ),
        query_anchor_coverage=(
            len(required_anchors.intersection(matched_anchors))
            / len(required_anchors)
            if required_anchors
            else None
        ),
        unique_query_term_count=len(unique_query_terms),
        unique_query_phrase_count=len(unique_query_phrases),
        source_type_count=len(source_type_counts),
        dominant_source_type=dominant_source_type,
        dominant_source_type_fraction=dominant_source_type_fraction,
        top_direct_relevance_margin=top_direct_relevance_margin,
        coverage_warnings=list(brief.coverage_warnings),
    )


def assess_evidence_quality_signals(
    metrics: EvidenceQualityMetrics,
    thresholds: Optional[EvidenceQualityThresholds] = None,
) -> EvidenceQualitySignals:
    thresholds = thresholds or EvidenceQualityThresholds()
    thresholds.validate()

    if thresholds.calibration_status == "unresolved":
        return EvidenceQualitySignals(
            metrics=metrics,
            thresholds=thresholds,
            evidence_sparse=None,
            evidence_ambiguous=None,
            source_diversity_low=None,
            unresolved_signal_names=[
                "evidence_sparse",
                "evidence_ambiguous",
                "source_diversity_low",
            ],
        )

    unresolved = []

    evidence_sparse = (
        metrics.direct_source_count
        < thresholds.sparse_direct_source_threshold
    )

    if metrics.top_direct_relevance_margin is None:
        evidence_ambiguous = None
        unresolved.append("evidence_ambiguous")
    else:
        evidence_ambiguous = (
            metrics.top_direct_relevance_margin
            <= thresholds.ambiguity_top_margin_threshold
        )

    if metrics.dominant_source_type_fraction is None:
        source_diversity_low = None
        unresolved.append("source_diversity_low")
    else:
        source_diversity_low = (
            metrics.dominant_source_type_fraction
            >= thresholds.low_diversity_fraction_threshold
        )

    return EvidenceQualitySignals(
        metrics=metrics,
        thresholds=thresholds,
        evidence_sparse=evidence_sparse,
        evidence_ambiguous=evidence_ambiguous,
        source_diversity_low=source_diversity_low,
        unresolved_signal_names=unresolved,
    )
