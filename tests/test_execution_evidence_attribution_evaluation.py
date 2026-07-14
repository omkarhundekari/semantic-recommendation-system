from datetime import datetime

import pytest
from pydantic import ValidationError

from execution_evidence.attribution_evaluation import (
    ATTRIBUTION_EVALUATION_DATASET_VERSION,
    ATTRIBUTION_EVALUATION_REPORT_VERSION,
    AttributionEvaluationCase,
    AttributionEvaluationDataset,
    evaluate_deterministic_attribution,
)
from execution_evidence.deterministic_attribution import (
    DETERMINISTIC_ATTRIBUTION_POLICY_VERSION,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
)
from planning.roadmap_snapshot import (
    build_roadmap_snapshot,
)
from schemas.product_models import RoadmapStage


NOW = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)


def _roadmap():
    return build_roadmap_snapshot(
        [
            RoadmapStage(
                id="mvp",
                title="Build retrieval MVP",
                purpose=(
                    "Implement document ingestion and "
                    "retrieval output."
                ),
                tasks=[
                    "Build document ingestion.",
                    "Write retrieval results.",
                ],
            ),
            RoadmapStage(
                id="validate",
                title="Validate retrieval quality",
                purpose=(
                    "Measure retrieval precision and "
                    "document failures."
                ),
                tasks=[
                    "Run evaluation questions.",
                    "Measure retrieval precision.",
                ],
            ),
            RoadmapStage(
                id="package",
                title="Package the project",
                purpose=(
                    "Publish a README, demo, and release."
                ),
            ),
        ]
    )


def _evidence(
    *,
    external_id,
    evidence_type="commit",
    title,
    description="",
):
    return ExecutionEvidenceItem(
        repository_full_name="owner/repository",
        evidence_type=evidence_type,
        external_id=external_id,
        title=title,
        description=description,
        url=(
            "https://github.com/owner/repository/"
            f"commit/{external_id}"
        ),
        occurred_at=NOW,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _dataset():
    roadmap = _roadmap()

    return AttributionEvaluationDataset(
        cases=[
            AttributionEvaluationCase(
                case_id="repo-a-mvp",
                repository_id="repo-a",
                evidence=_evidence(
                    external_id="mvp-1",
                    title=(
                        "Implement document ingestion "
                        "and retrieval output"
                    ),
                ),
                roadmap=roadmap,
                expected_roadmap_node_ids=["mvp"],
            ),
            AttributionEvaluationCase(
                case_id="repo-a-validate",
                repository_id="repo-a",
                evidence=_evidence(
                    external_id="validate-1",
                    evidence_type="workflow_run",
                    title=(
                        "Run retrieval precision "
                        "evaluation questions"
                    ),
                ),
                roadmap=roadmap,
                expected_roadmap_node_ids=[
                    "validate",
                ],
            ),
            AttributionEvaluationCase(
                case_id="repo-b-package",
                repository_id="repo-b",
                evidence=_evidence(
                    external_id="package-1",
                    evidence_type="release",
                    title=(
                        "Publish README demo release"
                    ),
                ),
                roadmap=roadmap,
                expected_roadmap_node_ids=[
                    "package",
                ],
            ),
            AttributionEvaluationCase(
                case_id="repo-b-abstain",
                repository_id="repo-b",
                evidence=_evidence(
                    external_id="unknown-1",
                    title="Update files",
                    description="Small changes.",
                ),
                roadmap=roadmap,
                expected_abstain=True,
            ),
        ]
    )


def test_evaluation_reports_expected_metrics():
    report = evaluate_deterministic_attribution(
        _dataset()
    )

    assert report.report_version == (
        ATTRIBUTION_EVALUATION_REPORT_VERSION
    )
    assert report.dataset_version == (
        ATTRIBUTION_EVALUATION_DATASET_VERSION
    )
    assert report.attribution_policy_version == (
        DETERMINISTIC_ATTRIBUTION_POLICY_VERSION
    )

    assert report.overall.case_count == 4
    assert (
        report.overall.attributable_case_count
        == 3
    )
    assert report.overall.suggestion_count == 3
    assert report.overall.abstention_count == 1
    assert report.overall.coverage == 0.75
    assert report.overall.top_1_precision == 1.0
    assert report.overall.top_2_recall == 1.0
    assert (
        report.overall.abstention_precision
        == 1.0
    )
    assert (
        report.overall
        .incorrect_suggestion_rate
        == 0.0
    )


def test_evaluation_reports_evidence_type_slices():
    report = evaluate_deterministic_attribution(
        _dataset()
    )

    assert set(report.by_evidence_type) == {
        "commit",
        "release",
        "workflow_run",
    }

    assert (
        report.by_evidence_type["release"]
        .top_1_precision
        == 1.0
    )
    assert (
        report.by_evidence_type["workflow_run"]
        .top_2_recall
        == 1.0
    )


def test_evaluation_preserves_repository_and_roadmap_provenance():
    report = evaluate_deterministic_attribution(
        _dataset()
    )

    assert report.repository_ids == [
        "repo-a",
        "repo-b",
    ]
    assert report.roadmap_hashes == [
        _roadmap().roadmap_hash
    ]


def test_evaluation_is_deterministic():
    dataset = _dataset()

    first = evaluate_deterministic_attribution(
        dataset
    )
    second = evaluate_deterministic_attribution(
        dataset.model_copy(deep=True)
    )

    assert first == second


def test_incorrect_suggestion_is_measured():
    roadmap = _roadmap()

    dataset = AttributionEvaluationDataset(
        cases=[
            AttributionEvaluationCase(
                case_id="incorrect-gold",
                repository_id="repo-a",
                evidence=_evidence(
                    external_id="incorrect-1",
                    title=(
                        "Implement document ingestion "
                        "and retrieval output"
                    ),
                ),
                roadmap=roadmap,
                expected_roadmap_node_ids=[
                    "validate",
                ],
            )
        ]
    )

    report = evaluate_deterministic_attribution(
        dataset
    )

    assert report.overall.suggestion_count == 1
    assert report.overall.top_1_precision == 0.0
    assert report.overall.top_2_recall in {
        0.0,
        1.0,
    }
    assert (
        report.overall
        .incorrect_suggestion_rate
        == 1.0
    )


def test_case_rejects_missing_expected_outcome():
    with pytest.raises(
        ValidationError,
        match="must define an expected",
    ):
        AttributionEvaluationCase(
            case_id="missing-gold",
            repository_id="repo-a",
            evidence=_evidence(
                external_id="missing-1",
                title="Update files",
            ),
            roadmap=_roadmap(),
        )


def test_case_rejects_attribution_and_abstention_together():
    with pytest.raises(
        ValidationError,
        match="cannot require both",
    ):
        AttributionEvaluationCase(
            case_id="conflicting-gold",
            repository_id="repo-a",
            evidence=_evidence(
                external_id="conflict-1",
                title="Update files",
            ),
            roadmap=_roadmap(),
            expected_roadmap_node_ids=["mvp"],
            expected_abstain=True,
        )


def test_case_rejects_unknown_roadmap_node():
    with pytest.raises(
        ValidationError,
        match="not present",
    ):
        AttributionEvaluationCase(
            case_id="unknown-node",
            repository_id="repo-a",
            evidence=_evidence(
                external_id="unknown-node-1",
                title="Build authentication",
            ),
            roadmap=_roadmap(),
            expected_roadmap_node_ids=[
                "authentication",
            ],
        )


def test_dataset_rejects_duplicate_case_ids():
    case = AttributionEvaluationCase(
        case_id="duplicate",
        repository_id="repo-a",
        evidence=_evidence(
            external_id="duplicate-1",
            title="Update files",
        ),
        roadmap=_roadmap(),
        expected_abstain=True,
    )

    with pytest.raises(
        ValidationError,
        match="case IDs must be unique",
    ):
        AttributionEvaluationDataset(
            cases=[
                case,
                case.model_copy(deep=True),
            ]
        )


def test_empty_dataset_produces_zero_metrics():
    report = evaluate_deterministic_attribution(
        AttributionEvaluationDataset(
            cases=[]
        )
    )

    assert report.overall.case_count == 0
    assert report.overall.coverage == 0.0
    assert report.overall.top_1_precision == 0.0
    assert report.overall.top_2_recall == 0.0
    assert report.overall.abstention_precision == 0.0
