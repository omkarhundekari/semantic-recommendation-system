from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from execution_evidence.coordinator import (
    StatefulGitHubSyncResult,
)
from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
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
from execution_evidence.sync import GitHubSyncResult
from product_api import (
    app,
    get_execution_evidence_coordinator,
)


REPOSITORY_URL = (
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

REFERENCE = parse_github_repository_url(
    REPOSITORY_URL
)

REPOSITORY_KEY = REFERENCE.repository_key

OBSERVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)


class FakeCoordinator:
    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def sync_repository(self, **kwargs):
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


def _successful_result():
    evidence = ExecutionEvidenceItem(
        repository_full_name=REFERENCE.full_name,
        evidence_type="commit",
        external_id="abc123",
        title="Expose execution evidence sync",
        url=(
            f"{REFERENCE.canonical_url}/commit/abc123"
        ),
        occurred_at=OBSERVED_AT,
        first_seen_at=OBSERVED_AT,
        last_seen_at=OBSERVED_AT,
    )

    state = RepositorySyncState(
        repository_key=REPOSITORY_KEY,
        status="succeeded",
        latest_commit_sha="abc123",
        last_attempted_at=OBSERVED_AT,
        last_succeeded_at=OBSERVED_AT,
    )

    snapshot = GitHubRepositorySyncSnapshot(
        repository_key=REPOSITORY_KEY,
    )

    sync = GitHubSyncResult(
        repository_key=REPOSITORY_KEY,
        status="succeeded",
        evidence=[evidence],
        sync_state=state,
        sync_snapshot=snapshot,
        synced_counts={"commit": 1},
        failed_types=[],
        errors={},
    )

    stored = StoredRepositoryEvidence(
        repository=REFERENCE,
        evidence=[evidence],
        sync_state=state,
        sync_snapshot=snapshot,
        revision=0,
        saved_at=OBSERVED_AT,
    )

    return StatefulGitHubSyncResult(
        sync=sync,
        stored=stored,
        created=True,
    )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_sync_endpoint_returns_persisted_execution_evidence(
    client,
):
    coordinator = FakeCoordinator(
        result=_successful_result(),
    )

    app.dependency_overrides[
        get_execution_evidence_coordinator
    ] = lambda: coordinator

    response = client.post(
        "/v1/execution-evidence/repositories/sync",
        json={
            "repository_url": REPOSITORY_URL,
            "since": "2026-07-01T00:00:00Z",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["created"] is True
    assert payload["sync"]["status"] == "succeeded"
    assert payload["sync"]["synced_counts"] == {
        "commit": 1,
    }
    assert payload["stored"]["revision"] == 0
    assert (
        payload["stored"]["evidence"][0]["external_id"]
        == "abc123"
    )

    assert len(coordinator.calls) == 1
    assert (
        coordinator.calls[0]["repository_url"]
        == REPOSITORY_URL
    )
    assert (
        coordinator.calls[0]["since"]
        == "2026-07-01T00:00:00Z"
    )
    assert coordinator.calls[0]["observed_at"].tzinfo


def test_sync_endpoint_maps_revision_conflict_to_409(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_coordinator
    ] = lambda: FakeCoordinator(
        error=RepositoryEvidenceConflictError(
            "Repository revision changed."
        )
    )

    response = client.post(
        "/v1/execution-evidence/repositories/sync",
        json={
            "repository_url": REPOSITORY_URL,
        },
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Repository revision changed."
    }


def test_sync_endpoint_maps_repository_validation_to_422(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_coordinator
    ] = lambda: FakeCoordinator(
        error=ValueError(
            "Only github.com repositories are supported."
        )
    )

    response = client.post(
        "/v1/execution-evidence/repositories/sync",
        json={
            "repository_url": (
                "https://gitlab.com/owner/repository"
            ),
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": (
            "Only github.com repositories are supported."
        )
    }


def test_sync_endpoint_requires_repository_url(
    client,
):
    app.dependency_overrides[
        get_execution_evidence_coordinator
    ] = lambda: FakeCoordinator(
        result=_successful_result()
    )

    response = client.post(
        "/v1/execution-evidence/repositories/sync",
        json={},
    )

    assert response.status_code == 422


class FakeRepositoryEvidenceStore:
    def __init__(
        self,
        *,
        record=None,
    ):
        self.record = record
        self.load_calls = []

    def load(self, repository_key):
        self.load_calls.append(repository_key)
        return self.record


def test_repository_endpoint_returns_stored_evidence(
    client,
):
    record = _successful_result().stored
    store = FakeRepositoryEvidenceStore(
        record=record,
    )

    from product_api import (
        get_execution_evidence_store,
    )

    app.dependency_overrides[
        get_execution_evidence_store
    ] = lambda: store

    response = client.get(
        (
            "/v1/execution-evidence/repositories/"
            "github:omkarhundekari/"
            "semantic-recommendation-system"
        )
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["revision"] == 0
    assert payload["repository"]["owner"] == (
        "omkarhundekari"
    )
    assert payload["evidence"][0]["external_id"] == (
        "abc123"
    )
    assert payload["attributions"] == []

    assert store.load_calls == [
        (
            "github:omkarhundekari/"
            "semantic-recommendation-system"
        )
    ]


def test_repository_endpoint_maps_missing_record_to_404(
    client,
):
    store = FakeRepositoryEvidenceStore()

    from product_api import (
        get_execution_evidence_store,
    )

    app.dependency_overrides[
        get_execution_evidence_store
    ] = lambda: store

    response = client.get(
        (
            "/v1/execution-evidence/repositories/"
            "github:owner/missing"
        )
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Repository evidence record was not found."
        )
    }


def test_repository_endpoint_preserves_repository_key_path(
    client,
):
    store = FakeRepositoryEvidenceStore()

    from product_api import (
        get_execution_evidence_store,
    )

    app.dependency_overrides[
        get_execution_evidence_store
    ] = lambda: store

    client.get(
        (
            "/v1/execution-evidence/repositories/"
            "github:MixedCase/Repository"
        )
    )

    assert store.load_calls == [
        "github:MixedCase/Repository"
    ]
