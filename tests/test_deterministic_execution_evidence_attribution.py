from datetime import datetime

import pytest

from execution_evidence.deterministic_attribution import (
    suggest_deterministic_attribution,
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


def _evidence(
    *,
    evidence_type="commit",
    title,
    description="",
    metadata=None,
):
    return ExecutionEvidenceItem(
        repository_full_name="owner/repository",
        evidence_type=evidence_type,
        external_id="abc123",
        title=title,
        description=description,
        url=(
            "https://github.com/"
            "owner/repository/commit/abc123"
        ),
        occurred_at=NOW,
        metadata=metadata or {},
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _roadmap():
    return build_roadmap_snapshot(
        [
            RoadmapStage(
                id="define",
                title="Define the problem",
                purpose=(
                    "Choose a user, input, output, "
                    "and success metric."
                ),
                tasks=[
                    "Write a measurable problem statement.",
                ],
                objective=(
                    "Define a constrained evaluation scope."
                ),
            ),
            RoadmapStage(
                id="mvp",
                title="Build the MVP",
                purpose=(
                    "Implement one complete retrieval workflow."
                ),
                tasks=[
                    "Build document ingestion.",
                    "Implement retrieval and result output.",
                ],
                objective=(
                    "Build one input-to-output retrieval path."
                ),
                commands=[
                    "python -m app",
                ],
                expected_outputs=[
                    "outputs/retrieval_results.json",
                ],
            ),
            RoadmapStage(
                id="validate",
                title="Validate retrieval quality",
                purpose=(
                    "Measure retrieval precision and "
                    "document failure cases."
                ),
                tasks=[
                    "Run evaluation questions.",
                    "Measure retrieval precision.",
                ],
                validation_checks=[
                    "Record retrieval_precision_at_3.",
                ],
            ),
            RoadmapStage(
                id="package",
                title="Package for portfolio",
                purpose=(
                    "Create a README, release, and demo."
                ),
                tasks=[
                    "Publish a release.",
                    "Document the architecture.",
                ],
            ),
        ]
    )


def test_clear_lexical_match_suggests_mvp_stage():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title=(
                "Implement document ingestion and "
                "retrieval result output"
            ),
            description=(
                "Adds the complete retrieval workflow "
                "and writes retrieval_results.json."
            ),
        ),
        roadmap=_roadmap(),
    )

    assert result.decision == "suggest"
    assert (
        result.candidates[0].roadmap_node_id
        == "mvp"
    )
    assert result.candidates[0].score > 0.20
    assert "retrieval" in (
        result.candidates[0].matched_terms
    )
    assert (
        result.candidates[0]
        .roadmap_context
        .roadmap_node_id
        == "mvp"
    )


def test_workflow_validation_evidence_prefers_validate():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            evidence_type="workflow_run",
            title="Run retrieval precision evaluation",
            description=(
                "Records retrieval_precision_at_3 "
                "for evaluation questions."
            ),
            metadata={
                "conclusion": "success",
                "branch": "validate-retrieval",
            },
        ),
        roadmap=_roadmap(),
    )

    assert result.decision == "suggest"
    assert (
        result.candidates[0].roadmap_node_id
        == "validate"
    )
    assert any(
        signal.name == "evidence_type_prior"
        for signal in result.candidates[0].signals
    )


def test_release_evidence_receives_package_prior():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            evidence_type="release",
            title="Publish portfolio demo release",
            description=(
                "Adds README architecture documentation "
                "and demo instructions."
            ),
            metadata={
                "tag_name": "v1.0.0",
            },
        ),
        roadmap=_roadmap(),
    )

    assert result.decision == "suggest"
    assert (
        result.candidates[0].roadmap_node_id
        == "package"
    )


def test_uninformative_activity_abstains():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title="Update files",
            description="Small changes.",
        ),
        roadmap=_roadmap(),
    )

    assert result.decision == "abstain"
    assert result.abstention_reason


def test_low_value_commit_is_penalized():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title="Fix typo in retrieval README",
            description="Formatting cleanup.",
        ),
        roadmap=_roadmap(),
        top_k=4,
    )

    package = next(
        candidate
        for candidate in result.candidates
        if candidate.roadmap_node_id
        == "package"
    )

    assert any(
        signal.name
        == "low_value_activity_penalty"
        and signal.contribution < 0
        for signal in package.signals
    )
    assert result.decision == "abstain"


def test_keyword_stuffing_is_capped():
    normal = suggest_deterministic_attribution(
        evidence=_evidence(
            title=(
                "Build retrieval workflow output"
            ),
        ),
        roadmap=_roadmap(),
    )

    stuffed = suggest_deterministic_attribution(
        evidence=_evidence(
            title=(
                "Build retrieval workflow output "
                + "retrieval " * 200
            ),
        ),
        roadmap=_roadmap(),
    )

    assert stuffed.top_score <= 1.0
    assert (
        stuffed.candidates[0].score
        == normal.candidates[0].score
    )


def test_thin_margin_abstains_between_similar_stages():
    roadmap = build_roadmap_snapshot(
        [
            RoadmapStage(
                id="mvp-a",
                title="Build retrieval API",
                purpose="Implement retrieval output.",
            ),
            RoadmapStage(
                id="mvp-b",
                title="Build retrieval service",
                purpose="Implement retrieval output.",
            ),
        ]
    )

    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title="Implement retrieval output",
            description="Build retrieval output.",
        ),
        roadmap=roadmap,
    )

    assert result.decision == "abstain"
    assert "too close" in result.abstention_reason


def test_top_two_candidates_are_deterministic():
    evidence = _evidence(
        title="Implement retrieval workflow",
        description="Add retrieval output.",
    )

    first = suggest_deterministic_attribution(
        evidence=evidence,
        roadmap=_roadmap(),
    )
    second = suggest_deterministic_attribution(
        evidence=evidence,
        roadmap=_roadmap(),
    )

    assert first == second
    assert len(first.candidates) == 2


def test_unicode_normalization_supports_matching():
    roadmap = build_roadmap_snapshot(
        [
            RoadmapStage(
                id="validate",
                title="Validate café recommendations",
                purpose=(
                    "Measure recommendation quality."
                ),
            )
        ]
    )

    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title=(
                "Validate cafe\u0301 recommendation "
                "quality"
            ),
        ),
        roadmap=roadmap,
    )

    assert result.decision == "suggest"
    assert (
        result.candidates[0].roadmap_node_id
        == "validate"
    )


def test_invisible_characters_do_not_break_matching():
    result = suggest_deterministic_attribution(
        evidence=_evidence(
            title=(
                "Implement retriev\u200bal workflow "
                "output"
            ),
            description=(
                "Build document ingestion and retrieval."
            ),
        ),
        roadmap=_roadmap(),
    )

    assert (
        result.candidates[0].roadmap_node_id
        == "mvp"
    )


def test_invalid_top_k_is_rejected():
    with pytest.raises(
        ValueError,
        match="top_k must be at least 1",
    ):
        suggest_deterministic_attribution(
            evidence=_evidence(
                title="Implement retrieval workflow",
            ),
            roadmap=_roadmap(),
            top_k=0,
        )
