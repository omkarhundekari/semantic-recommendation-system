from datetime import datetime

import pytest
from pydantic import ValidationError

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    EvidenceAttribution,
    RoadmapAttributionContext,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    StoredRepositoryEvidence,
)


SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

REPOSITORY_KEY = REFERENCE.repository_key


def _evidence() -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id="abc123",
        title="Add repository evidence store",
        url=(
            f"{REFERENCE.canonical_url}/commit/"
            "abc123"
        ),
        occurred_at=SAVED_AT,
        first_seen_at=SAVED_AT,
        last_seen_at=SAVED_AT,
    )


def _base_record_payload() -> dict:
    return {
        "repository": REFERENCE,
        "sync_state": RepositorySyncState(
            repository_key=REPOSITORY_KEY,
        ),
        "sync_snapshot": GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
        ),
        "saved_at": SAVED_AT,
    }


def test_record_rejects_mismatched_sync_state():
    with pytest.raises(
        ValidationError,
        match="sync state does not match",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            sync_state=RepositorySyncState(
                repository_key=(
                    "github:other/repository"
                ),
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=REPOSITORY_KEY,
            ),
            saved_at=SAVED_AT,
        )


def test_record_rejects_mismatched_sync_snapshot():
    with pytest.raises(
        ValidationError,
        match="sync snapshot does not match",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            sync_state=RepositorySyncState(
                repository_key=REPOSITORY_KEY,
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=(
                    "github:other/repository"
                ),
            ),
            saved_at=SAVED_AT,
        )


def test_record_rejects_evidence_from_other_repository():
    foreign_evidence = _evidence().model_copy(
        update={
            "repository_full_name":
                "other/repository",
        }
    )

    with pytest.raises(
        ValidationError,
        match="different repository",
    ):
        StoredRepositoryEvidence(
            evidence=[foreign_evidence],
            **_base_record_payload(),
        )


def test_record_rejects_attribution_for_missing_evidence():
    attribution = EvidenceAttribution(
        evidence_key=(
            "github:omkarhundekari/"
            "semantic-recommendation-system:"
            "commit:missing"
        ),
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1,
        rationale="",
        status="accepted",
        decided_at=SAVED_AT,
    )

    with pytest.raises(
        ValidationError,
        match="does not exist",
    ):
        StoredRepositoryEvidence(
            attributions=[attribution],
            **_base_record_payload(),
        )


def test_record_rejects_duplicate_attributions():
    evidence = _evidence()
    attribution = EvidenceAttribution(
        evidence_key=evidence.evidence_key,
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1,
        rationale="",
        status="accepted",
        decided_at=SAVED_AT,
    )

    with pytest.raises(
        ValidationError,
        match="duplicate attributions",
    ):
        StoredRepositoryEvidence(
            evidence=[evidence],
            attributions=[
                attribution,
                attribution.model_copy(deep=True),
            ],
            **_base_record_payload(),
        )


def _durable_attribution(
    *,
    evidence_key: str,
    project_id: str,
    roadmap_snapshot_id: str,
    attribution_id: str,
) -> EvidenceAttribution:
    return EvidenceAttribution(
        attribution_id=attribution_id,
        project_id=project_id,
        roadmap_snapshot_id=roadmap_snapshot_id,
        evidence_key=evidence_key,
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        rationale="",
        status="accepted",
        decided_at=SAVED_AT,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash="a" * 64,
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="build-mvp",
            snapshot_version=1,
            canonicalization_version=1,
        ),
    )


def test_record_allows_same_link_across_durable_snapshots():
    evidence = _evidence()

    first = _durable_attribution(
        evidence_key=evidence.evidence_key,
        project_id="proj_one",
        roadmap_snapshot_id="snap_one",
        attribution_id="attribution-one",
    )
    second = _durable_attribution(
        evidence_key=evidence.evidence_key,
        project_id="proj_one",
        roadmap_snapshot_id="snap_two",
        attribution_id="attribution-two",
    )

    record = StoredRepositoryEvidence(
        evidence=[evidence],
        attributions=[first, second],
        **_base_record_payload(),
    )

    assert len(record.attributions) == 2
    assert {
        attribution.roadmap_snapshot_id
        for attribution in record.attributions
    } == {"snap_one", "snap_two"}


def test_record_rejects_duplicate_link_in_durable_snapshot():
    evidence = _evidence()
    attribution = _durable_attribution(
        evidence_key=evidence.evidence_key,
        project_id="proj_one",
        roadmap_snapshot_id="snap_one",
        attribution_id="attribution-one",
    )

    duplicate = attribution.model_copy(
        update={
            "attribution_id": "attribution-two",
        },
        deep=True,
    )

    with pytest.raises(
        ValidationError,
        match="duplicate attributions",
    ):
        StoredRepositoryEvidence(
            evidence=[evidence],
            attributions=[
                attribution,
                duplicate,
            ],
            **_base_record_payload(),
        )
