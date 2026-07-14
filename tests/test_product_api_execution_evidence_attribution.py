from datetime import datetime
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from execution_evidence.attribution import (
    AttributionContextConflictError,
    AttributionMutationResult,
    ExecutionEvidenceNotFoundError,
    RepositoryEvidenceNotFoundError,
)
from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from planning.roadmap_registry import (
    RoadmapRegistryError,
    StoredRoadmapSnapshot,
)
from planning.roadmap_snapshot import (
    RoadmapSnapshot,
    RoadmapStageSnapshot,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    RepositoryEvidenceConflictError,
    StoredRepositoryEvidence,
)
from product_api import (
    app,
    get_execution_evidence_attribution_service,
    get_roadmap_snapshot_registry,
)


NOW = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)

REPOSITORY_KEY = REFERENCE.repository_key
PROJECT_DIRECTION_ID = "trusted-project-direction"

TRUSTED_ROADMAP = StoredRoadmapSnapshot(
    project_direction_id=PROJECT_DIRECTION_ID,
    response_direction_id="direction-1",
    title="Trusted project direction",
    snapshot=RoadmapSnapshot(
        roadmap_hash="a" * 64,
        stages=[
            RoadmapStageSnapshot(
                stage_id="build-mvp",
                position=0,
                content_hash="b" * 64,
                content={
                    "id": "build-mvp",
                    "title": "Build the MVP",
                },
            )
        ],
    ),
    created_at=datetime.fromisoformat(
        "2026-07-13T12:00:00+00:00"
    ),
)

EVIDENCE = ExecutionEvidenceItem(
    repository_full_name=REFERENCE.full_name,
    evidence_type="commit",
    external_id="abc123",
    title="Implement attribution API",
    url=f"{REFERENCE.canonical_url}/commit/abc123",
    occurred_at=NOW,
    first_seen_at=NOW,
    last_seen_at=NOW,
)

ATTRIBUTION = EvidenceAttribution(
    evidence_key=EVIDENCE.evidence_key,
    roadmap_node_id="build-mvp",
    source="manual",
    confidence=1.0,
    rationale="This commit completes the MVP stage.",
    status="accepted",
    decided_at=NOW,
)


def _stored_record(
    *,
    revision: int = 1,
):
    return StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[EVIDENCE],
        attributions=[ATTRIBUTION],
        sync_state=RepositorySyncState(
            repository_key=REPOSITORY_KEY,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=REPOSITORY_KEY,
        ),
        revision=revision,
        saved_at=NOW,
    )


class FakeRoadmapRegistry:
    def __init__(
        self,
        *,
        record: Optional[
            StoredRoadmapSnapshot
        ] = TRUSTED_ROADMAP,
        error: Optional[Exception] = None,
    ):
        self.record = record
        self.error = error
        self.load_calls = []

    def load(
        self,
        project_direction_id: str,
    ):
        self.load_calls.append(
            project_direction_id
        )

        if self.error is not None:
            raise self.error

        if (
            self.record is not None
            and self.record.project_direction_id
            == project_direction_id
        ):
            return self.record

        return None


class FakeAttributionService:
    def __init__(
        self,
        *,
        attach_result=None,
        detach_result=False,
        list_result=None,
        error=None,
    ):
        self.attach_result = attach_result
        self.detach_result = detach_result
        self.list_result = (
            list_result
            if list_result is not None
            else []
        )
        self.error = error
        self.attach_calls = []
        self.detach_calls = []
        self.list_repository_calls = []
        self.list_node_calls = []

    def attach(self, **kwargs):
        self.attach_calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.attach_result

    def detach(self, **kwargs):
        self.detach_calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.detach_result

    def list_for_repository(
        self,
        repository_key,
        *,
        project_direction_id=None,
    ):
        self.list_repository_calls.append(
            {
                "repository_key": repository_key,
                "project_direction_id": (
                    project_direction_id
                ),
            }
        )

        if self.error is not None:
            raise self.error

        return self.list_result

    def list_for_roadmap_node(self, **kwargs):
        self.list_node_calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.list_result


@pytest.fixture
def client():
    app.dependency_overrides[
        get_roadmap_snapshot_registry
    ] = lambda: FakeRoadmapRegistry()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_attach_endpoint_returns_updated_record(
    client,
):
    service = FakeAttributionService(
        attach_result=AttributionMutationResult(
            stored=_stored_record(),
            attribution=ATTRIBUTION,
            created=True,
        )
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
            "rationale": (
                "This commit completes the MVP stage."
            ),
            "expected_revision": 0,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["created"] is True
    assert payload["stored"]["revision"] == 1
    assert (
        payload["attribution"]["roadmap_node_id"]
        == "build-mvp"
    )

    call = service.attach_calls[0]

    assert call["repository_key"] == REPOSITORY_KEY
    assert call["evidence_key"] == EVIDENCE.evidence_key
    assert call["expected_revision"] == 0
    assert (
        call["project_direction_id"]
        == PROJECT_DIRECTION_ID
    )
    assert call["decided_at"].tzinfo
    assert (
        call["roadmap_context"].roadmap_hash
        == TRUSTED_ROADMAP.snapshot.roadmap_hash
    )
    assert (
        call["roadmap_context"].roadmap_stage_hash
        == TRUSTED_ROADMAP.snapshot.stages[0].content_hash
    )
    assert (
        call["roadmap_context"].roadmap_node_id
        == "build-mvp"
    )


def test_attach_endpoint_maps_missing_evidence_to_404(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=ExecutionEvidenceNotFoundError(
            "Execution evidence item was not found."
        )
    )

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Execution evidence item was not found."
        )
    }


def test_attach_endpoint_maps_conflict_to_409(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceConflictError(
            "Repository evidence revision conflict."
        )
    )

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 409


def test_detach_endpoint_returns_removal_status(
    client,
):
    service = FakeAttributionService(
        detach_result=True
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.request(
        "DELETE",
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "removed": True,
    }

    call = service.detach_calls[0]

    assert call["expected_revision"] == 1
    assert (
        call["project_direction_id"]
        == PROJECT_DIRECTION_ID
    )
    assert call["removed_at"].tzinfo



def test_detach_endpoint_maps_conflict_to_409(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceConflictError(
            "Repository evidence revision conflict."
        )
    )

    response = client.request(
        "DELETE",
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Repository evidence revision conflict."
        )
    }



def test_detach_endpoint_maps_missing_repository_to_404(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceNotFoundError(
            "Repository evidence record was not found."
        )
    )

    response = client.request(
        "DELETE",
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
            "expected_revision": 1,
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Repository evidence record was not found."
        )
    }


def test_list_endpoint_returns_repository_links(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["evidence_key"] == (
        EVIDENCE.evidence_key
    )
    assert service.list_repository_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
        }
    ]


def test_list_endpoint_filters_by_roadmap_node(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert service.list_node_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        }
    ]



@pytest.mark.parametrize(
    "field_name",
    [
        "repository_key",
        "project_direction_id",
        "roadmap_node_id",
    ],
)
def test_list_endpoint_rejects_blank_identity_fields(
    client,
    field_name,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    params = {
        "repository_key": REPOSITORY_KEY,
        "project_direction_id": (
            PROJECT_DIRECTION_ID
        ),
        "roadmap_node_id": "build-mvp",
    }
    params[field_name] = "   "

    response = client.get(
        "/v1/execution-evidence/attributions",
        params=params,
    )

    assert response.status_code == 422
    assert service.list_repository_calls == []
    assert service.list_node_calls == []


def test_list_endpoint_trims_repository_scope(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": f"  {REPOSITORY_KEY}  ",
            "project_direction_id": (
                f"  {PROJECT_DIRECTION_ID}  "
            ),
        },
    )

    assert response.status_code == 200
    assert service.list_repository_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
        }
    ]
    assert service.list_node_calls == []


def test_list_node_endpoint_trims_identity_fields(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": f"  {REPOSITORY_KEY}  ",
            "project_direction_id": (
                f"  {PROJECT_DIRECTION_ID}  "
            ),
            "roadmap_node_id": "  build-mvp  ",
        },
    )

    assert response.status_code == 200
    assert service.list_node_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        }
    ]
    assert service.list_repository_calls == []


def test_list_endpoint_maps_missing_repository_to_404(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceNotFoundError(
            "Repository evidence record was not found."
        )
    )

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
        },
    )

    assert response.status_code == 404



def test_list_node_endpoint_maps_missing_repository_to_404(
    client,
):
    service = FakeAttributionService(
        error=RepositoryEvidenceNotFoundError(
            "Repository evidence record was not found."
        )
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        "/v1/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Repository evidence record was not found."
        )
    }
    assert service.list_node_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        }
    ]
    assert service.list_repository_calls == []


def test_attach_endpoint_maps_context_conflict_to_409(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=AttributionContextConflictError(
            "Evidence attribution already exists "
            "with different roadmap identity context."
        )
    )

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Evidence attribution already exists "
            "with different roadmap identity context."
        )
    }



def test_attach_endpoint_requires_trusted_registry(
    client,
):
    app.dependency_overrides[
        get_roadmap_snapshot_registry
    ] = lambda: None

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 503
    assert "trusted SQLite" in response.json()["detail"]


def test_attach_endpoint_rejects_unknown_project_snapshot(
    client,
):
    app.dependency_overrides[
        get_roadmap_snapshot_registry
    ] = lambda: FakeRoadmapRegistry(
        record=None
    )

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": "unknown",
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Trusted project direction snapshot "
            "was not found."
        )
    }


def test_attach_endpoint_rejects_node_outside_snapshot(
    client,
):
    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "unknown-stage",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Roadmap node does not belong to the "
            "trusted project direction snapshot."
        )
    }


def test_attach_endpoint_maps_registry_failure_to_503(
    client,
):
    app.dependency_overrides[
        get_roadmap_snapshot_registry
    ] = lambda: FakeRoadmapRegistry(
        error=RoadmapRegistryError(
            "Registry unavailable."
        )
    )

    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 503



@pytest.mark.parametrize(
    "field_name",
    [
        "project_direction_id",
        "repository_key",
        "evidence_key",
        "roadmap_node_id",
    ],
)
def test_attach_endpoint_rejects_blank_identity_fields(
    client,
    field_name,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    payload = {
        "project_direction_id": PROJECT_DIRECTION_ID,
        "repository_key": REPOSITORY_KEY,
        "evidence_key": EVIDENCE.evidence_key,
        "roadmap_node_id": "build-mvp",
    }
    payload[field_name] = "   "

    response = client.post(
        "/v1/execution-evidence/attributions",
        json=payload,
    )

    assert response.status_code == 422
    assert service.attach_calls == []


@pytest.mark.parametrize(
    "field_name",
    [
        "project_direction_id",
        "repository_key",
        "evidence_key",
        "roadmap_node_id",
    ],
)
def test_detach_endpoint_rejects_blank_identity_fields(
    client,
    field_name,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    payload = {
        "project_direction_id": PROJECT_DIRECTION_ID,
        "repository_key": REPOSITORY_KEY,
        "evidence_key": EVIDENCE.evidence_key,
        "roadmap_node_id": "build-mvp",
    }
    payload[field_name] = "   "

    response = client.request(
        "DELETE",
        "/v1/execution-evidence/attributions",
        json=payload,
    )

    assert response.status_code == 422
    assert service.detach_calls == []


def test_attribution_request_identity_fields_are_trimmed(
    client,
):
    service = FakeAttributionService(
        detach_result=False
    )

    app.dependency_overrides[
        get_execution_evidence_attribution_service
    ] = lambda: service

    response = client.request(
        "DELETE",
        "/v1/execution-evidence/attributions",
        json={
            "project_direction_id": (
                f"  {PROJECT_DIRECTION_ID}  "
            ),
            "repository_key": f"  {REPOSITORY_KEY}  ",
            "evidence_key": (
                f"  {EVIDENCE.evidence_key}  "
            ),
            "roadmap_node_id": "  build-mvp  ",
        },
    )

    assert response.status_code == 200
    assert service.detach_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "removed_at": (
                service.detach_calls[0]["removed_at"]
            ),
            "expected_revision": None,
        }
    ]


def test_attach_endpoint_requires_project_direction_id(
    client,
):
    response = client.post(
        "/v1/execution-evidence/attributions",
        json={
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 422
