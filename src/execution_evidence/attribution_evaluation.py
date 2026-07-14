from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from pydantic import BaseModel, Field, model_validator

from execution_evidence.deterministic_attribution import (
    DETERMINISTIC_ATTRIBUTION_POLICY_VERSION,
    DeterministicAttributionSuggestion,
    suggest_deterministic_attribution,
)
from execution_evidence.models import (
    EvidenceType,
    ExecutionEvidenceItem,
)
from planning.roadmap_snapshot import RoadmapSnapshot


ATTRIBUTION_EVALUATION_DATASET_VERSION = 1
ATTRIBUTION_EVALUATION_REPORT_VERSION = 1


class AttributionEvaluationCase(BaseModel):
    case_id: str = Field(min_length=1)
    repository_id: str = Field(min_length=1)
    evidence: ExecutionEvidenceItem
    roadmap: RoadmapSnapshot
    expected_roadmap_node_ids: List[str] = Field(
        default_factory=list
    )
    expected_abstain: bool = False

    @model_validator(mode="after")
    def validate_expected_outcome(
        self,
    ) -> "AttributionEvaluationCase":
        normalized_nodes = [
            node_id.strip()
            for node_id in self.expected_roadmap_node_ids
        ]

        if any(not node_id for node_id in normalized_nodes):
            raise ValueError(
                "Expected roadmap node IDs must be non-empty."
            )

        if len(normalized_nodes) != len(
            set(normalized_nodes)
        ):
            raise ValueError(
                "Expected roadmap node IDs must be unique."
            )

        if self.expected_abstain and normalized_nodes:
            raise ValueError(
                "An evaluation case cannot require both "
                "attribution and abstention."
            )

        if not self.expected_abstain and not normalized_nodes:
            raise ValueError(
                "An evaluation case must define an expected "
                "roadmap node or expected abstention."
            )

        roadmap_node_ids = {
            stage.stage_id
            for stage in self.roadmap.stages
        }

        missing_nodes = [
            node_id
            for node_id in normalized_nodes
            if node_id not in roadmap_node_ids
        ]

        if missing_nodes:
            raise ValueError(
                "Expected roadmap nodes are not present in "
                "the case roadmap: "
                + ", ".join(sorted(missing_nodes))
                + "."
            )

        self.expected_roadmap_node_ids = normalized_nodes
        return self


class AttributionEvaluationDataset(BaseModel):
    dataset_version: int = (
        ATTRIBUTION_EVALUATION_DATASET_VERSION
    )
    cases: List[AttributionEvaluationCase]

    @model_validator(mode="after")
    def validate_case_identity(
        self,
    ) -> "AttributionEvaluationDataset":
        case_ids = [
            case.case_id
            for case in self.cases
        ]

        if len(case_ids) != len(set(case_ids)):
            raise ValueError(
                "Attribution evaluation case IDs "
                "must be unique."
            )

        return self


class AttributionEvaluationCaseResult(BaseModel):
    case_id: str
    repository_id: str
    evidence_type: EvidenceType
    expected_roadmap_node_ids: List[str]
    expected_abstain: bool
    predicted_roadmap_node_ids: List[str]
    predicted_abstain: bool
    top_1_correct: bool
    top_2_correct: bool
    abstention_correct: bool
    suggestion: DeterministicAttributionSuggestion


class AttributionEvaluationMetrics(BaseModel):
    case_count: int = Field(ge=0)
    attributable_case_count: int = Field(ge=0)
    expected_abstention_count: int = Field(ge=0)
    suggestion_count: int = Field(ge=0)
    abstention_count: int = Field(ge=0)

    top_1_correct_count: int = Field(ge=0)
    top_2_correct_count: int = Field(ge=0)
    correct_abstention_count: int = Field(ge=0)
    incorrect_suggestion_count: int = Field(ge=0)

    coverage: float = Field(ge=0.0, le=1.0)
    top_1_precision: float = Field(ge=0.0, le=1.0)
    top_2_recall: float = Field(ge=0.0, le=1.0)
    abstention_precision: float = Field(
        ge=0.0,
        le=1.0,
    )
    incorrect_suggestion_rate: float = Field(
        ge=0.0,
        le=1.0,
    )


class AttributionEvaluationReport(BaseModel):
    report_version: int = (
        ATTRIBUTION_EVALUATION_REPORT_VERSION
    )
    dataset_version: int
    attribution_policy_version: int
    repository_ids: List[str]
    roadmap_hashes: List[str]
    overall: AttributionEvaluationMetrics
    by_evidence_type: Dict[
        str,
        AttributionEvaluationMetrics
    ]
    cases: List[AttributionEvaluationCaseResult]


def evaluate_deterministic_attribution(
    dataset: AttributionEvaluationDataset,
) -> AttributionEvaluationReport:
    case_results = [
        _evaluate_case(case)
        for case in dataset.cases
    ]

    grouped: Dict[
        str,
        List[AttributionEvaluationCaseResult],
    ] = defaultdict(list)

    for result in case_results:
        grouped[result.evidence_type].append(result)

    return AttributionEvaluationReport(
        dataset_version=dataset.dataset_version,
        attribution_policy_version=(
            DETERMINISTIC_ATTRIBUTION_POLICY_VERSION
        ),
        repository_ids=sorted(
            {
                case.repository_id
                for case in dataset.cases
            }
        ),
        roadmap_hashes=sorted(
            {
                case.roadmap.roadmap_hash
                for case in dataset.cases
            }
        ),
        overall=_calculate_metrics(case_results),
        by_evidence_type={
            evidence_type: _calculate_metrics(results)
            for evidence_type, results in sorted(
                grouped.items()
            )
        },
        cases=case_results,
    )


def _evaluate_case(
    case: AttributionEvaluationCase,
) -> AttributionEvaluationCaseResult:
    suggestion = suggest_deterministic_attribution(
        evidence=case.evidence,
        roadmap=case.roadmap,
        top_k=2,
    )

    predicted_node_ids = [
        candidate.roadmap_node_id
        for candidate in suggestion.candidates
    ]

    predicted_abstain = (
        suggestion.decision == "abstain"
    )
    expected_nodes = set(
        case.expected_roadmap_node_ids
    )

    top_1_correct = bool(
        not predicted_abstain
        and predicted_node_ids
        and predicted_node_ids[0] in expected_nodes
    )
    top_2_correct = bool(
        expected_nodes.intersection(
            predicted_node_ids[:2]
        )
    )
    abstention_correct = bool(
        case.expected_abstain
        and predicted_abstain
    )

    return AttributionEvaluationCaseResult(
        case_id=case.case_id,
        repository_id=case.repository_id,
        evidence_type=case.evidence.evidence_type,
        expected_roadmap_node_ids=(
            case.expected_roadmap_node_ids
        ),
        expected_abstain=case.expected_abstain,
        predicted_roadmap_node_ids=predicted_node_ids,
        predicted_abstain=predicted_abstain,
        top_1_correct=top_1_correct,
        top_2_correct=top_2_correct,
        abstention_correct=abstention_correct,
        suggestion=suggestion,
    )


def _calculate_metrics(
    results: List[AttributionEvaluationCaseResult],
) -> AttributionEvaluationMetrics:
    case_count = len(results)
    attributable = [
        result
        for result in results
        if not result.expected_abstain
    ]
    expected_abstentions = [
        result
        for result in results
        if result.expected_abstain
    ]
    suggestions = [
        result
        for result in results
        if not result.predicted_abstain
    ]
    abstentions = [
        result
        for result in results
        if result.predicted_abstain
    ]

    top_1_correct_count = sum(
        result.top_1_correct
        for result in suggestions
    )
    top_2_correct_count = sum(
        result.top_2_correct
        for result in attributable
    )
    correct_abstention_count = sum(
        result.abstention_correct
        for result in abstentions
    )

    incorrect_suggestion_count = sum(
        not result.top_1_correct
        for result in suggestions
    )

    return AttributionEvaluationMetrics(
        case_count=case_count,
        attributable_case_count=len(attributable),
        expected_abstention_count=(
            len(expected_abstentions)
        ),
        suggestion_count=len(suggestions),
        abstention_count=len(abstentions),
        top_1_correct_count=top_1_correct_count,
        top_2_correct_count=top_2_correct_count,
        correct_abstention_count=(
            correct_abstention_count
        ),
        incorrect_suggestion_count=(
            incorrect_suggestion_count
        ),
        coverage=_ratio(
            len(suggestions),
            case_count,
        ),
        top_1_precision=_ratio(
            top_1_correct_count,
            len(suggestions),
        ),
        top_2_recall=_ratio(
            top_2_correct_count,
            len(attributable),
        ),
        abstention_precision=_ratio(
            correct_abstention_count,
            len(abstentions),
        ),
        incorrect_suggestion_rate=_ratio(
            incorrect_suggestion_count,
            len(suggestions),
        ),
    )


def _ratio(
    numerator: int,
    denominator: int,
) -> float:
    if denominator == 0:
        return 0.0

    return round(
        numerator / denominator,
        6,
    )
