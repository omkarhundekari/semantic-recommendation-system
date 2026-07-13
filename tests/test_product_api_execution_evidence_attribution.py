from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from execution_evidence.attribution import (
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
)


NOW = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REFERENCE = parse_github_repository_url(
    "https://github.com/owner/repository"
)

REPOSITORY_KEY = REFERENCE.repository_key

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

    def list_for_repository(self, repository_key):
        self.list_repository_calls.append(
            repository_key
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
    assert call["decided_at"].tzinfo


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
    assert call["removed_at"].tzinfo


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
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["evidence_key"] == (
        EVIDENCE.evidence_key
    )
    assert service.list_repository_calls == [
        REPOSITORY_KEY
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
            "roadmap_node_id": "build-mvp",
        },
    )

    assert response.status_code == 200
    assert service.list_node_calls == [
        {
            "repository_key": REPOSITORY_KEY,
            "roadmap_node_id": "build-mvp",
        }
    ]


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
        },
    )

    assert response.status_code == 404
