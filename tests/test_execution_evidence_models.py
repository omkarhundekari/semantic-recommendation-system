from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RoadmapAttributionContext,
)


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def test_evidence_identity_ignores_mutable_display_fields():
    original = ExecutionEvidenceItem(
        repository_full_name="omkarhundekari/solvyn",
        evidence_type="pull_request",
        external_id="42",
        title="Open pull request",
        description="Initial description",
        url="https://github.com/omkarhundekari/solvyn/pull/42",
        occurred_at=_timestamp("2026-07-13T00:00:00Z"),
        metadata={"state": "open"},
        first_seen_at=_timestamp("2026-07-13T00:01:00Z"),
        last_seen_at=_timestamp("2026-07-13T00:01:00Z"),
    )

    refreshed = original.model_copy(
        update={
            "title": "Merged pull request",
            "metadata": {"state": "closed", "merged": True},
        }
    )

    assert original.evidence_key == refreshed.evidence_key
    assert original.evidence_key == (
        "github:"
        "omkarhundekari/solvyn:"
        "pull_request:"
        "42"
    )


def test_attribution_identity_is_evidence_and_roadmap_specific():
    attribution = EvidenceAttribution(
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="validate",
        source="manual",
        confidence=1.0,
        rationale="The commit adds the evaluation fixture.",
        status="accepted",
        decided_at=datetime.now(timezone.utc),
    )

    assert attribution.attribution_key == (
        "github:owner/repo:commit:abc123:validate"
    )


def test_project_scoped_attribution_has_stable_identity():
    context = RoadmapAttributionContext(
        roadmap_hash="a" * 64,
        roadmap_stage_hash="b" * 64,
        roadmap_node_id="validate",
        snapshot_version=1,
        canonicalization_version=1,
    )

    attribution = EvidenceAttribution(
        attribution_id="attribution-123",
        project_direction_id="project-123",
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="validate",
        source="manual",
        confidence=1.0,
        status="accepted",
        roadmap_context=context,
    )

    assert attribution.attribution_identity == (
        "direction",
        "project-123",
        "github:owner/repo:commit:abc123",
        "validate",
    )


def test_same_evidence_and_stage_can_belong_to_two_projects():
    first = EvidenceAttribution(
        attribution_id="attribution-1",
        project_direction_id="project-1",
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash="a" * 64,
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="build-mvp",
            snapshot_version=1,
            canonicalization_version=1,
        ),
    )
    second = first.model_copy(
        update={
            "attribution_id": "attribution-2",
            "project_direction_id": "project-2",
        }
    )

    assert (
        first.attribution_identity
        != second.attribution_identity
    )


def test_project_scope_requires_stable_attribution_id():
    with pytest.raises(
        ValidationError,
        match="requires attribution_id",
    ):
        EvidenceAttribution(
            project_direction_id="project-123",
            evidence_key="github:owner/repo:commit:abc123",
            roadmap_node_id="build-mvp",
            source="manual",
            confidence=1.0,
            roadmap_context=RoadmapAttributionContext(
                roadmap_hash="a" * 64,
                roadmap_stage_hash="b" * 64,
                roadmap_node_id="build-mvp",
                snapshot_version=1,
                canonicalization_version=1,
            ),
        )


def test_project_scope_requires_trusted_context():
    with pytest.raises(
        ValidationError,
        match="requires trusted roadmap context",
    ):
        EvidenceAttribution(
            attribution_id="attribution-123",
            project_direction_id="project-123",
            evidence_key="github:owner/repo:commit:abc123",
            roadmap_node_id="build-mvp",
            source="manual",
            confidence=1.0,
        )


def test_legacy_contextual_attribution_remains_readable():
    attribution = EvidenceAttribution(
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash="a" * 64,
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="build-mvp",
            snapshot_version=1,
            canonicalization_version=1,
        ),
    )

    assert attribution.attribution_id is None
    assert attribution.project_direction_id is None


def test_attribution_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        EvidenceAttribution(
            evidence_key="github:owner/repo:commit:abc123",
            roadmap_node_id="mvp",
            source="deterministic",
            confidence=1.2,
        )


def test_attribution_preserves_roadmap_identity_context():
    from execution_evidence.models import (
        RoadmapAttributionContext,
    )

    context = RoadmapAttributionContext(
        roadmap_hash="a" * 64,
        roadmap_stage_hash="b" * 64,
        roadmap_node_id="mvp",
        snapshot_version=1,
        canonicalization_version=1,
    )

    attribution = EvidenceAttribution(
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="mvp",
        source="manual",
        confidence=1.0,
        status="accepted",
        roadmap_context=context,
    )

    restored = EvidenceAttribution.model_validate_json(
        attribution.model_dump_json()
    )

    assert restored.roadmap_context == context


def test_attribution_rejects_mismatched_roadmap_context():
    from execution_evidence.models import (
        RoadmapAttributionContext,
    )

    with pytest.raises(
        ValidationError,
        match="must match roadmap_node_id",
    ):
        EvidenceAttribution(
            evidence_key="github:owner/repo:commit:abc123",
            roadmap_node_id="mvp",
            source="manual",
            confidence=1.0,
            roadmap_context=RoadmapAttributionContext(
                roadmap_hash="a" * 64,
                roadmap_stage_hash="b" * 64,
                roadmap_node_id="validate",
                snapshot_version=1,
                canonicalization_version=1,
            ),
        )


def test_roadmap_context_rejects_invalid_hashes():
    from execution_evidence.models import (
        RoadmapAttributionContext,
    )

    with pytest.raises(ValidationError):
        RoadmapAttributionContext(
            roadmap_hash="not-a-hash",
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="mvp",
            snapshot_version=1,
            canonicalization_version=1,
        )


def test_attribution_preserves_durable_project_identity():
    context = RoadmapAttributionContext(
        roadmap_hash="a" * 64,
        roadmap_stage_hash="b" * 64,
        roadmap_node_id="validate",
        snapshot_version=1,
        canonicalization_version=1,
    )

    attribution = EvidenceAttribution(
        attribution_id="attribution-123",
        project_id="proj_123",
        roadmap_snapshot_id="snap_123",
        project_direction_id="direction-123",
        evidence_key="github:owner/repo:commit:abc123",
        roadmap_node_id="validate",
        source="manual",
        confidence=1.0,
        status="accepted",
        roadmap_context=context,
    )

    restored = EvidenceAttribution.model_validate_json(
        attribution.model_dump_json()
    )

    assert restored.project_id == "proj_123"
    assert (
        restored.roadmap_snapshot_id
        == "snap_123"
    )
    assert (
        restored.project_direction_id
        == "direction-123"
    )


def test_attribution_accepts_durable_identity_without_alias():
    attribution = EvidenceAttribution(
        attribution_id="attribution-one",
        project_id="proj_one",
        roadmap_snapshot_id="snap_one",
        evidence_key=(
            "github:owner/repository:commit:abc123"
        ),
        roadmap_node_id="validate",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=None,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash="a" * 64,
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="validate",
            snapshot_version=1,
            canonicalization_version=1,
        ),
    )

    assert attribution.durable_scope == (
        "proj_one",
        "snap_one",
    )
    assert attribution.project_direction_id is None


@pytest.mark.parametrize(
    ("project_id", "roadmap_snapshot_id"),
    [
        ("proj_one", None),
        (None, "snap_one"),
    ],
)
def test_attribution_rejects_partial_durable_identity(
    project_id,
    roadmap_snapshot_id,
):
    with pytest.raises(
        ValueError,
        match=(
            "Durable attribution identity requires "
            "both project_id and roadmap_snapshot_id"
        ),
    ):
        EvidenceAttribution(
            attribution_id="attribution-one",
            project_id=project_id,
            roadmap_snapshot_id=roadmap_snapshot_id,
            evidence_key=(
                "github:owner/repository:commit:abc123"
            ),
            roadmap_node_id="validate",
            source="manual",
            confidence=1.0,
            status="accepted",
            decided_at=None,
            roadmap_context=RoadmapAttributionContext(
                roadmap_hash="a" * 64,
                roadmap_stage_hash="b" * 64,
                roadmap_node_id="validate",
                snapshot_version=1,
                canonicalization_version=1,
            ),
        )


def test_attribution_id_rejects_missing_roadmap_scope():
    with pytest.raises(
        ValueError,
        match=(
            "Attribution ID requires a durable "
            "or direction roadmap identity"
        ),
    ):
        EvidenceAttribution(
            attribution_id="attribution-one",
            evidence_key=(
                "github:owner/repository:commit:abc123"
            ),
            roadmap_node_id="validate",
            source="manual",
            confidence=1.0,
            status="accepted",
            decided_at=None,
        )
