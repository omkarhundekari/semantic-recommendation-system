from types import SimpleNamespace
from datetime import datetime
from typing import Optional

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
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
    RoadmapAttributionContext,
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
    get_authorized_execution_evidence_attribution_service,
    get_authorized_project_context,
    get_authorized_roadmap_registry,
)


NOW = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)

REPOSITORY_KEY = REFERENCE.repository_key
PROJECT_DIRECTION_ID = "trusted-project-direction"
PROJECT_ID = "proj_trusted"
ROADMAP_SNAPSHOT_ID = "snap_trusted"
WORKSPACE_ID = "workspace-attribution-test"
PRINCIPAL_ID = "prn_123e4567-e89b-42d3-a456-426614174000"
MEMBERSHIP_ID = "wsm_123e4567-e89b-42d3-a456-426614174003"

TRUSTED_ROADMAP = StoredRoadmapSnapshot(
    project_id=PROJECT_ID,
    roadmap_snapshot_id=ROADMAP_SNAPSHOT_ID,
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
        self.durable_load_calls = []
        self.durable_load_calls = []

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

    def load_by_snapshot_id(
        self,
        roadmap_snapshot_id: str,
    ):
        if self.error is not None:
            raise self.error

        if (
            self.record is not None
            and self.record.roadmap_snapshot_id
            == roadmap_snapshot_id
        ):
            return self.record

        return None

    def load_by_durable_identity(
        self,
        *,
        project_id: str,
        roadmap_snapshot_id: str,
    ):
        self.durable_load_calls.append(
            {
                "project_id": project_id,
                "roadmap_snapshot_id": (
                    roadmap_snapshot_id
                ),
            }
        )

        if self.error is not None:
            raise self.error

        if (
            self.record is not None
            and self.record.project_id
            == project_id
            and self.record.roadmap_snapshot_id
            == roadmap_snapshot_id
        ):
            return self.record

        return None

    def load_by_snapshot_id(
        self,
        roadmap_snapshot_id: str,
    ):
        if self.error is not None:
            raise self.error

        if (
            self.record is not None
            and self.record.roadmap_snapshot_id
            == roadmap_snapshot_id
        ):
            return self.record

        return None

    def load_by_durable_identity(
        self,
        *,
        project_id: str,
        roadmap_snapshot_id: str,
    ):
        self.durable_load_calls.append(
            {
                "project_id": project_id,
                "roadmap_snapshot_id": (
                    roadmap_snapshot_id
                ),
            }
        )

        if self.error is not None:
            raise self.error

        if (
            self.record is not None
            and self.record.project_id
            == project_id
            and self.record.roadmap_snapshot_id
            == roadmap_snapshot_id
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
        project_id=None,
        roadmap_snapshot_id=None,
        project_direction_id=None,
    ):
        self.list_repository_calls.append(
            {
                "repository_key": repository_key,
                "project_id": project_id,
                "roadmap_snapshot_id": (
                    roadmap_snapshot_id
                ),
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
    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="admin",
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )

    app.dependency_overrides[
        get_authorized_project_context
    ] = lambda: context
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry()
    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService()

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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=ExecutionEvidenceNotFoundError(
            "Execution evidence item was not found."
        )
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceConflictError(
            "Repository evidence revision conflict."
        )
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
    assert call["project_id"] == PROJECT_ID
    assert (
        call["roadmap_snapshot_id"]
        == ROADMAP_SNAPSHOT_ID
    )
    assert (
        call["project_direction_id"]
        == PROJECT_DIRECTION_ID
    )
    assert call["removed_at"].tzinfo



def test_detach_endpoint_maps_conflict_to_409(
    client,
):
    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceConflictError(
            "Repository evidence revision conflict."
        )
    )

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceNotFoundError(
            "Repository evidence record was not found."
        )
    )

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
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
        get_authorized_execution_evidence_attribution_service
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
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=RepositoryEvidenceNotFoundError(
            "Repository evidence record was not found."
        )
    )

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: FakeAttributionService(
        error=AttributionContextConflictError(
            "Evidence attribution already exists "
            "with different roadmap identity context."
        )
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
    def unavailable_registry():
        raise HTTPException(
            status_code=503,
            detail=(
                "Trusted project lifecycle storage is "
                "unavailable. Migrate execution evidence "
                "storage to trusted SQLite first."
            ),
        )

    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = unavailable_registry

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry(
        record=None
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry(
        error=RoadmapRegistryError(
            "Registry unavailable."
        )
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    payload = {
        "project_direction_id": PROJECT_DIRECTION_ID,
        "repository_key": REPOSITORY_KEY,
        "evidence_key": EVIDENCE.evidence_key,
        "roadmap_node_id": "build-mvp",
    }
    payload[field_name] = "   "

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
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
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
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
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "removed_at": (
                service.detach_calls[0]["removed_at"]
            ),
            "expected_revision": None,
        }
    ]


def test_attach_endpoint_requires_roadmap_identity(
    client,
):
    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 422


def test_attach_endpoint_returns_durable_identity(
    client,
):
    durable_attribution = EvidenceAttribution(
        attribution_id="attribution-one",
        project_id=PROJECT_ID,
        roadmap_snapshot_id=ROADMAP_SNAPSHOT_ID,
        project_direction_id=PROJECT_DIRECTION_ID,
        evidence_key=EVIDENCE.evidence_key,
        roadmap_node_id="build-mvp",
        source="manual",
        confidence=1.0,
        status="accepted",
        decided_at=NOW,
        roadmap_context=RoadmapAttributionContext(
            roadmap_hash="a" * 64,
            roadmap_stage_hash="b" * 64,
            roadmap_node_id="build-mvp",
            snapshot_version=1,
            canonicalization_version=1,
        ),
    )
    service = FakeAttributionService(
        attach_result=AttributionMutationResult(
            stored=_stored_record(),
            attribution=durable_attribution,
            created=True,
        )
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    payload = response.json()["attribution"]

    assert payload["project_id"] == PROJECT_ID
    assert (
        payload["roadmap_snapshot_id"]
        == ROADMAP_SNAPSHOT_ID
    )
    assert (
        payload["project_direction_id"]
        == PROJECT_DIRECTION_ID
    )

    call = service.attach_calls[0]

    assert call["project_id"] == PROJECT_ID
    assert (
        call["roadmap_snapshot_id"]
        == ROADMAP_SNAPSHOT_ID
    )


@pytest.mark.parametrize(
    ("field_name", "field_value", "detail"),
    [
        (
            "roadmap_snapshot_id",
            "snap_wrong",
            (
                "roadmap_snapshot_id does not match the "
                "trusted project direction snapshot."
            ),
        ),
    ],
)
def test_attach_endpoint_rejects_mismatched_durable_identity(
    client,
    field_name,
    field_value,
    detail,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    payload = {
        "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
        "project_direction_id": PROJECT_DIRECTION_ID,
        "repository_key": REPOSITORY_KEY,
        "evidence_key": EVIDENCE.evidence_key,
        "roadmap_node_id": "build-mvp",
    }
    payload[field_name] = field_value

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json=payload,
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": detail,
    }
    assert service.attach_calls == []


def test_list_endpoint_validates_supplied_durable_identity(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
        },
    )

    assert response.status_code == 200
    assert len(response.json()) == 1

def test_attach_endpoint_accepts_durable_identity_only(
    client,
):
    service = FakeAttributionService(
        attach_result=AttributionMutationResult(
            stored=_stored_record(),
            attribution=ATTRIBUTION,
            created=True,
        )
    )
    registry = FakeRoadmapRegistry()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: registry

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert registry.load_calls == []
    assert registry.durable_load_calls == [
        {
            "project_id": PROJECT_ID,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
        }
    ]

    call = service.attach_calls[0]

    assert (
        call["project_direction_id"]
        == PROJECT_DIRECTION_ID
    )
    assert call["project_id"] == PROJECT_ID
    assert (
        call["roadmap_snapshot_id"]
        == ROADMAP_SNAPSHOT_ID
    )


def test_detach_endpoint_accepts_durable_identity_only(
    client,
):
    service = FakeAttributionService(
        detach_result=True
    )
    registry = FakeRoadmapRegistry()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: registry

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "removed": True,
    }
    assert (
        service.detach_calls[0]["project_id"]
        == PROJECT_ID
    )
    assert (
        service.detach_calls[0][
            "roadmap_snapshot_id"
        ]
        == ROADMAP_SNAPSHOT_ID
    )
    assert (
        service.detach_calls[0][
            "project_direction_id"
        ]
        == PROJECT_DIRECTION_ID
    )


def test_list_endpoint_accepts_durable_identity_only(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )
    registry = FakeRoadmapRegistry()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: registry

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
        },
    )

    assert response.status_code == 200
    assert service.list_repository_calls == [
        {
            "repository_key": REPOSITORY_KEY,
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
        }
    ]


def test_list_node_endpoint_accepts_durable_identity_only(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert service.list_node_calls == [
        {
            "repository_key": REPOSITORY_KEY,
                "project_id": PROJECT_ID,
            "roadmap_snapshot_id": (
                ROADMAP_SNAPSHOT_ID
            ),
            "project_direction_id": (
                PROJECT_DIRECTION_ID
            ),
            "roadmap_node_id": "build-mvp",
        }
    ]


def test_attach_endpoint_rejects_caller_project_id(
    client,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions",
        json={
            "project_id": PROJECT_ID,
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 422
    assert service.attach_calls == []


def test_roadmap_snapshot_id_is_complete_with_authorized_project(
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
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert service.attach_calls[0]["project_id"] == PROJECT_ID


def test_attach_endpoint_rejects_missing_roadmap_identity(
    client,
):
    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 422


def test_attach_endpoint_rejects_conflicting_direction_alias(
    client,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "project_direction_id": "wrong-direction",
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 404
    assert service.attach_calls == []



@pytest.mark.parametrize(
    "project_status",
    ["archived", "deleted"],
)
def test_attach_endpoint_rejects_inactive_project(
    client,
    project_status: str,
):
    service = FakeAttributionService()
    inactive_roadmap = TRUSTED_ROADMAP.model_copy(
        update={
            "project_status": project_status,
        },
        deep=True,
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry(
        record=inactive_roadmap
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Cannot attach new execution evidence "
            f"to a {project_status} project."
        )
    }
    assert service.attach_calls == []


@pytest.mark.parametrize(
    "project_status",
    ["archived", "deleted"],
)
def test_detach_endpoint_allows_inactive_project(
    client,
    project_status: str,
):
    service = FakeAttributionService(
        detach_result=True
    )
    inactive_roadmap = TRUSTED_ROADMAP.model_copy(
        update={
            "project_status": project_status,
        },
        deep=True,
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry(
        record=inactive_roadmap
    )

    response = client.request(
        "DELETE",
        f"/v1/workspaces/{WORKSPACE_ID}/projects/{PROJECT_ID}/execution-evidence/attributions",
        json={
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "removed": True,
    }
    assert len(service.detach_calls) == 1


def test_project_id_is_not_accepted_in_attribution_body(
    client,
):
    service = FakeAttributionService()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions",
        json={
            "project_id": PROJECT_ID,
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 422
    assert service.attach_calls == []


def test_cross_project_direction_is_hidden_before_store_operation(
    client,
):
    service = FakeAttributionService()
    other_project = TRUSTED_ROADMAP.model_copy(
        update={
            "project_id": "proj_other",
        }
    )

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: FakeRoadmapRegistry(
        record=other_project
    )

    response = client.post(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions",
        json={
            "project_direction_id": PROJECT_DIRECTION_ID,
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
    assert service.attach_calls == []


def test_viewer_can_list_attributions_but_cannot_mutate(
    client,
):
    viewer_context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role="viewer",
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )

    app.dependency_overrides[
        get_authorized_project_context
    ] = lambda: viewer_context
    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    path = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    listed = client.get(
        path,
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": PROJECT_DIRECTION_ID,
        },
    )
    attached = client.post(
        path,
        json={
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )
    detached = client.request(
        "DELETE",
        path,
        json={
            "project_direction_id": PROJECT_DIRECTION_ID,
            "repository_key": REPOSITORY_KEY,
            "evidence_key": EVIDENCE.evidence_key,
            "roadmap_node_id": "build-mvp",
        },
    )

    assert listed.status_code == 200

    assert attached.status_code == 403
    assert attached.json()["detail"] == (
        "Project capability is required: "
        "execution_evidence.mutate."
    )

    assert detached.status_code == 403
    assert detached.json()["detail"] == (
        "Project capability is required: "
        "execution_evidence.mutate."
    )

    assert service.attach_calls == []
    assert service.detach_calls == []


def test_unassigned_role_has_no_attribution_capabilities(
    client,
):
    context = AuthorizedProjectContext(
        principal_id=PRINCIPAL_ID,
        membership_id=MEMBERSHIP_ID,
        membership_role=None,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
    )
    service = FakeAttributionService()

    app.dependency_overrides[
        get_authorized_project_context
    ] = lambda: context
    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service

    path = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    listed = client.get(
        path,
        params={
            "repository_key": REPOSITORY_KEY,
            "project_direction_id": PROJECT_DIRECTION_ID,
        },
    )

    assert listed.status_code == 403
    assert listed.json()["detail"] == (
        "Project capability is required: "
        "execution_evidence.read."
    )

    assert service.list_repository_calls == []
    assert service.list_node_calls == []


def test_old_global_attribution_routes_are_unregistered():
    with TestClient(app) as test_client:
        post_response = test_client.post(
            "/v1/execution-evidence/attributions",
            json={},
        )
        delete_response = test_client.request(
            "DELETE",
            "/v1/execution-evidence/attributions",
            json={},
        )
        get_response = test_client.get(
            "/v1/execution-evidence/attributions"
        )

    assert post_response.status_code == 404
    assert delete_response.status_code == 404
    assert get_response.status_code == 404


def test_attribution_routes_require_authentication_before_access():
    from execution_evidence.project_access_service import (
        ProjectAccessService,
    )
    from product_api import (
        get_project_access_service,
        get_authentication_runtime,
    )

    class FailingAuthenticator:
        def authenticate(self, token):
            from execution_evidence.request_authenticator import (
                RequestAuthenticationRequiredError,
            )

            raise RequestAuthenticationRequiredError(
                "Authentication is required."
            )

    class RecordingAccessService(ProjectAccessService):
        def __init__(self):
            self.calls = []

        def authorize(
            self,
            *,
            principal,
            workspace_id,
            project_id,
        ):
            self.calls.append(
                {
                    "principal": principal,
                    "workspace_id": workspace_id,
                    "project_id": project_id,
                }
            )
            raise AssertionError(
                "Project authorization must not run "
                "before authentication succeeds."
            )

    access = RecordingAccessService()

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: SimpleNamespace(
            ready=True,
            authenticator=FailingAuthenticator(),
        )
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access

    path_value = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                path_value,
                params={
                    "repository_key": REPOSITORY_KEY,
                    "project_direction_id": (
                        PROJECT_DIRECTION_ID
                    ),
                },
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"
    assert access.calls == []


def test_inaccessible_attribution_project_is_404_not_403():
    from execution_evidence.project_access_service import (
        ProjectAccessNotFoundError,
        ProjectAccessService,
    )
    from product_api import (
        get_project_access_service,
        get_authentication_runtime,
    )

    class SuccessfulAuthenticator:
        def authenticate(self, token):
            from execution_evidence.authenticated_request_principal import (
                AuthenticatedRequestPrincipal,
            )

            return AuthenticatedRequestPrincipal(
                principal_id=PRINCIPAL_ID,
                identity_provider_id=(
                    "idp_123e4567-e89b-42d3-a456-426614174001"
                ),
                identity_link_id=(
                    "pil_123e4567-e89b-42d3-a456-426614174002"
                ),
                issuer="https://issuer.example",
                subject="subject-123",
            )

    class InaccessibleProjectAccessService(
        ProjectAccessService
    ):
        def authorize(
            self,
            *,
            principal,
            workspace_id,
            project_id,
        ):
            raise ProjectAccessNotFoundError(
                "Project does not exist."
            )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: SimpleNamespace(
            ready=True,
            authenticator=SuccessfulAuthenticator(),
        )
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: InaccessibleProjectAccessService()

    path_value = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    try:
        with TestClient(app) as test_client:
            response = test_client.get(
                path_value,
                params={
                    "repository_key": REPOSITORY_KEY,
                    "project_direction_id": (
                        PROJECT_DIRECTION_ID
                    ),
                },
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Project does not exist."
    }


def test_authorized_project_identity_is_authoritative_for_durable_lookup(
    client,
):
    service = FakeAttributionService(
        list_result=[ATTRIBUTION]
    )
    registry = FakeRoadmapRegistry()

    app.dependency_overrides[
        get_authorized_execution_evidence_attribution_service
    ] = lambda: service
    app.dependency_overrides[
        get_authorized_roadmap_registry
    ] = lambda: registry

    response = client.get(
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions",
        params={
            "repository_key": REPOSITORY_KEY,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
        },
    )

    assert response.status_code == 200

    assert registry.durable_load_calls == [
        {
            "project_id": PROJECT_ID,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
        }
    ]

    assert service.list_repository_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "project_id": PROJECT_ID,
            "roadmap_snapshot_id": ROADMAP_SNAPSHOT_ID,
            "project_direction_id": PROJECT_DIRECTION_ID,
        }
    ]


def test_attribution_query_validation_occurs_after_authentication():
    from execution_evidence.project_access_service import (
        ProjectAccessService,
    )
    from execution_evidence.request_authenticator import (
        RequestAuthenticationRequiredError,
    )
    from product_api import (
        get_project_access_service,
        get_authentication_runtime,
    )

    class FailingAuthenticator:
        def authenticate(self, header):
            raise RequestAuthenticationRequiredError(
                "Authentication is required."
            )

    class RecordingAccessService(ProjectAccessService):
        def __init__(self):
            self.calls = []

        def authorize(
            self,
            *,
            principal,
            workspace_id,
            project_id,
        ):
            self.calls.append(
                (
                    principal,
                    workspace_id,
                    project_id,
                )
            )
            raise AssertionError(
                "Authorization must not run before "
                "authentication succeeds."
            )

    access = RecordingAccessService()

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: SimpleNamespace(
            ready=True,
            authenticator=FailingAuthenticator(),
        )
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: access

    path_value = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    try:
        with TestClient(app) as test_client:
            # Intentionally omit repository_key and roadmap identity.
            # If query validation ran first, this would be 422.
            response = test_client.get(
                path_value,
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.headers[
        "www-authenticate"
    ] == "Bearer"
    assert access.calls == []


def test_attribution_query_validation_occurs_after_tenancy():
    from execution_evidence.authenticated_request_principal import (
        AuthenticatedRequestPrincipal,
    )
    from execution_evidence.project_access_service import (
        ProjectAccessNotFoundError,
        ProjectAccessService,
    )
    from product_api import (
        get_project_access_service,
        get_authentication_runtime,
    )

    class SuccessfulAuthenticator:
        def authenticate(self, header):
            return AuthenticatedRequestPrincipal(
                principal_id=PRINCIPAL_ID,
                identity_provider_id=(
                    "idp_123e4567-e89b-42d3-a456-426614174001"
                ),
                identity_link_id=(
                    "pil_123e4567-e89b-42d3-a456-426614174002"
                ),
                issuer="https://issuer.example",
                subject="subject-123",
            )

    class InaccessibleProjectAccessService(
        ProjectAccessService
    ):
        def authorize(
            self,
            *,
            principal,
            workspace_id,
            project_id,
        ):
            raise ProjectAccessNotFoundError(
                "Project does not exist."
            )

    app.dependency_overrides[
        get_authentication_runtime
    ] = lambda: SimpleNamespace(
            ready=True,
            authenticator=SuccessfulAuthenticator(),
        )
    app.dependency_overrides[
        get_project_access_service
    ] = lambda: InaccessibleProjectAccessService()

    path_value = (
        f"/v1/workspaces/{WORKSPACE_ID}/projects/"
        f"{PROJECT_ID}/execution-evidence/attributions"
    )

    try:
        with TestClient(app) as test_client:
            # Again intentionally malformed. Tenancy failure must hide
            # query-contract details and remain 404 rather than 422.
            response = test_client.get(
                path_value,
                headers={
                    "Authorization": "Bearer token",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Project does not exist."
    }
