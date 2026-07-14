from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from execution_evidence.attribution import (
    EvidenceAttributionService,
    ExecutionEvidenceNotFoundError,
    RepositoryEvidenceNotFoundError,
)
from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.json_store import (
    JsonRepositoryEvidenceStore,
)
from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    InMemoryRepositoryEvidenceStore,
    RepositoryEvidenceConflictError,
    StoredRepositoryEvidence,
)


NOW = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

LATER = datetime.fromisoformat(
    "2026-07-13T13:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)

REPOSITORY_KEY = REFERENCE.repository_key


def _evidence() -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id="abc123",
        title="Implement attribution persistence",
        url=(
            f"{REFERENCE.canonical_url}/commit/abc123"
        ),
        occurred_at=NOW,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def _record() -> StoredRepositoryEvidence:
    return StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[_evidence()],
        sync_state=RepositorySyncState(
            repository_key=REPOSITORY_KEY,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
        ),
        saved_at=NOW,
    )


def test_attach_creates_manual_accepted_attribution():
    store = InMemoryRepositoryEvidenceStore()
    saved = store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    result = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="validate-system",
        rationale="This commit completes validation.",
        decided_at=LATER,
    )

    assert result.created is True
    assert result.stored.revision == 1
    assert result.attribution.source == "manual"
    assert result.attribution.status == "accepted"
    assert result.attribution.confidence == 1.0
    assert (
        result.attribution.roadmap_node_id
        == "validate-system"
    )
    assert saved.attributions == []


def test_duplicate_attach_is_idempotent():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    first = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )

    second = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=LATER,
    )

    assert first.created is True
    assert second.created is False
    assert second.stored.revision == 1
    assert len(second.stored.attributions) == 1


def test_same_evidence_can_support_multiple_stages():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )
    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="validate-system",
        decided_at=LATER,
    )

    attributions = service.list_for_repository(
        REPOSITORY_KEY
    )

    assert {
        item.roadmap_node_id
        for item in attributions
    } == {
        "build-mvp",
        "validate-system",
    }


def test_detach_removes_link_without_removing_evidence():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    attached = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )

    removed = service.detach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        removed_at=LATER,
        expected_revision=(
            attached.stored.revision
        ),
    )

    loaded = store.load(REPOSITORY_KEY)

    assert removed is True
    assert loaded is not None
    assert loaded.attributions == []
    assert len(loaded.evidence) == 1
    assert loaded.revision == 2


def test_detach_missing_link_is_idempotent():
    store = InMemoryRepositoryEvidenceStore()
    saved = store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    removed = service.detach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="missing-stage",
        removed_at=LATER,
    )

    loaded = store.load(REPOSITORY_KEY)

    assert removed is False
    assert loaded == saved


def test_attach_requires_existing_repository():
    service = EvidenceAttributionService(
        store=InMemoryRepositoryEvidenceStore()
    )

    with pytest.raises(
        RepositoryEvidenceNotFoundError,
        match="was not found",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=_evidence().evidence_key,
            roadmap_node_id="build-mvp",
            decided_at=NOW,
        )


def test_attach_requires_existing_evidence():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    with pytest.raises(
        ExecutionEvidenceNotFoundError,
        match="item was not found",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=(
                "github:owner/repository:"
                "commit:missing"
            ),
            roadmap_node_id="build-mvp",
            decided_at=NOW,
        )


def test_attach_surfaces_revision_conflict():
    store = InMemoryRepositoryEvidenceStore()
    first = store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    store.save(
        first,
        expected_revision=first.revision,
    )

    with pytest.raises(
        RepositoryEvidenceConflictError,
        match="revision conflict",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=_evidence().evidence_key,
            roadmap_node_id="build-mvp",
            decided_at=NOW,
            expected_revision=first.revision,
        )


def test_list_for_roadmap_node_filters_links():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )
    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="validate-system",
        decided_at=LATER,
    )

    filtered = service.list_for_roadmap_node(
        repository_key=REPOSITORY_KEY,
        roadmap_node_id="validate-system",
    )

    assert len(filtered) == 1
    assert (
        filtered[0].roadmap_node_id
        == "validate-system"
    )


def test_attributions_survive_json_store_restart(
    tmp_path: Path,
):
    store_path = tmp_path / "repositories.json"
    first_store = JsonRepositoryEvidenceStore(
        store_path
    )
    first_store.save(_record())

    EvidenceAttributionService(
        store=first_store
    ).attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )

    restarted_store = JsonRepositoryEvidenceStore(
        store_path
    )
    loaded = restarted_store.load(REPOSITORY_KEY)

    assert loaded is not None
    assert len(loaded.attributions) == 1
    assert (
        loaded.attributions[0].roadmap_node_id
        == "build-mvp"
    )


def test_record_rejects_attribution_for_missing_evidence():
    attribution = EvidenceAttribution(
        evidence_key=(
            "github:owner/repository:commit:missing"
        ),
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=NOW,
    )

    with pytest.raises(
        ValidationError,
        match="does not exist",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            evidence=[_evidence()],
            attributions=[attribution],
            sync_state=RepositorySyncState(
                repository_key=REPOSITORY_KEY,
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=REPOSITORY_KEY,
            ),
            saved_at=NOW,
        )


def test_record_rejects_duplicate_attributions():
    attribution = EvidenceAttribution(
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=NOW,
    )

    with pytest.raises(
        ValidationError,
        match="duplicate attributions",
    ):
        StoredRepositoryEvidence(
            repository=REFERENCE,
            evidence=[_evidence()],
            attributions=[
                attribution,
                attribution.model_copy(deep=True),
            ],
            sync_state=RepositorySyncState(
                repository_key=REPOSITORY_KEY,
            ),
            sync_snapshot=GitHubRepositorySyncSnapshot(
                repository_key=REPOSITORY_KEY,
            ),
            saved_at=NOW,
        )


def test_attach_stamps_trusted_roadmap_context():
    from execution_evidence.models import (
        RoadmapAttributionContext,
    )

    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    context = RoadmapAttributionContext(
        roadmap_hash="a" * 64,
        roadmap_stage_hash="b" * 64,
        roadmap_node_id="build-mvp",
        snapshot_version=1,
        canonicalization_version=1,
    )

    result = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        roadmap_context=context,
        decided_at=NOW,
    )

    assert (
        result.attribution.roadmap_context
        == context
    )

    loaded = store.load(REPOSITORY_KEY)

    assert loaded is not None
    assert (
        loaded.attributions[0].roadmap_context
        == context
    )


def test_legacy_attach_remains_context_optional():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    result = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )

    assert (
        result.attribution.roadmap_context
        is None
    )


def _roadmap_context(
    *,
    roadmap_hash: str = "a" * 64,
    stage_hash: str = "b" * 64,
):
    from execution_evidence.models import (
        RoadmapAttributionContext,
    )

    return RoadmapAttributionContext(
        roadmap_hash=roadmap_hash,
        roadmap_stage_hash=stage_hash,
        roadmap_node_id="build-mvp",
        snapshot_version=1,
        canonicalization_version=1,
    )


def test_duplicate_attach_with_same_context_is_idempotent():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )
    context = _roadmap_context()

    first = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        roadmap_context=context,
        decided_at=NOW,
    )

    second = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        roadmap_context=context.model_copy(deep=True),
        decided_at=LATER,
    )

    assert first.created is True
    assert second.created is False
    assert second.stored.revision == 1
    assert second.attribution.roadmap_context == context


def test_duplicate_attach_rejects_changed_stage_context():
    from execution_evidence.attribution import (
        AttributionContextConflictError,
    )

    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        roadmap_context=_roadmap_context(),
        decided_at=NOW,
    )

    with pytest.raises(
        AttributionContextConflictError,
        match="different roadmap identity context",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=_evidence().evidence_key,
            roadmap_node_id="build-mvp",
            roadmap_context=_roadmap_context(
                stage_hash="c" * 64,
            ),
            decided_at=LATER,
        )


def test_legacy_attribution_is_not_silently_upgraded():
    from execution_evidence.attribution import (
        AttributionContextConflictError,
    )

    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )

    with pytest.raises(
        AttributionContextConflictError,
        match="different roadmap identity context",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=_evidence().evidence_key,
            roadmap_node_id="build-mvp",
            roadmap_context=_roadmap_context(),
            decided_at=LATER,
        )


def test_contextual_attribution_is_not_silently_downgraded():
    from execution_evidence.attribution import (
        AttributionContextConflictError,
    )

    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        roadmap_context=_roadmap_context(),
        decided_at=NOW,
    )

    with pytest.raises(
        AttributionContextConflictError,
        match="different roadmap identity context",
    ):
        service.attach(
            repository_key=REPOSITORY_KEY,
            evidence_key=_evidence().evidence_key,
            roadmap_node_id="build-mvp",
            decided_at=LATER,
        )


def test_project_scoped_attach_generates_stable_identity():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )
    context = _roadmap_context()

    first = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        roadmap_context=context,
        decided_at=NOW,
    )

    second = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        roadmap_context=context.model_copy(
            deep=True
        ),
        decided_at=LATER,
    )

    assert first.created is True
    assert second.created is False
    assert first.attribution.attribution_id is not None
    assert (
        second.attribution.attribution_id
        == first.attribution.attribution_id
    )
    assert (
        first.attribution.project_direction_id
        == "project-one"
    )


def test_same_evidence_stage_can_be_scoped_to_two_projects():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    first = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        roadmap_context=_roadmap_context(),
        decided_at=NOW,
    )

    second = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-two",
        roadmap_context=_roadmap_context(),
        decided_at=LATER,
    )

    assert first.created is True
    assert second.created is True
    assert (
        first.attribution.attribution_id
        != second.attribution.attribution_id
    )
    assert len(
        service.list_for_repository(
            REPOSITORY_KEY
        )
    ) == 2


def test_detach_removes_only_matching_project_scope():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    first = service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        roadmap_context=_roadmap_context(),
        decided_at=NOW,
    )
    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-two",
        roadmap_context=_roadmap_context(),
        decided_at=LATER,
    )

    removed = service.detach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        removed_at=LATER,
        expected_revision=first.stored.revision + 1,
    )

    remaining = service.list_for_repository(
        REPOSITORY_KEY
    )

    assert removed is True
    assert len(remaining) == 1
    assert (
        remaining[0].project_direction_id
        == "project-two"
    )


def test_repository_listing_filters_project_scope():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-one",
        roadmap_context=_roadmap_context(),
        decided_at=NOW,
    )
    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        project_direction_id="project-two",
        roadmap_context=_roadmap_context(),
        decided_at=LATER,
    )

    filtered = service.list_for_repository(
        REPOSITORY_KEY,
        project_direction_id="project-two",
    )

    assert len(filtered) == 1
    assert (
        filtered[0].project_direction_id
        == "project-two"
    )


def test_project_listing_excludes_legacy_attributions():
    store = InMemoryRepositoryEvidenceStore()
    store.save(_record())
    service = EvidenceAttributionService(
        store=store
    )

    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="build-mvp",
        decided_at=NOW,
    )
    service.attach(
        repository_key=REPOSITORY_KEY,
        evidence_key=_evidence().evidence_key,
        roadmap_node_id="validate-system",
        project_direction_id="project-one",
        roadmap_context=(
            _roadmap_context().model_copy(
                update={
                    "roadmap_node_id": (
                        "validate-system"
                    ),
                }
            )
        ),
        decided_at=LATER,
    )

    filtered = service.list_for_repository(
        REPOSITORY_KEY,
        project_direction_id="project-one",
    )

    assert len(filtered) == 1
    assert (
        filtered[0].project_direction_id
        == "project-one"
    )
