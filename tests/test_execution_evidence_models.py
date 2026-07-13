from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
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


def test_attribution_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        EvidenceAttribution(
            evidence_key="github:owner/repo:commit:abc123",
            roadmap_node_id="mvp",
            source="deterministic",
            confidence=1.2,
        )
