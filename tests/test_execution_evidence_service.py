from datetime import datetime
from typing import Dict, Optional

import pytest

from execution_evidence.github_client import (
    GitHubClientError,
    GitHubFetchResult,
)
from execution_evidence.models import (
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.service import (
    GitHubExecutionEvidenceService,
)


OBSERVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)

REPOSITORY_URL = (
    "https://github.com/omkarhundekari/"
    "semantic-recommendation-system"
)

REPOSITORY_KEY = (
    "github:omkarhundekari/semantic-recommendation-system"
)


class FakeGitHubClient:
    def __init__(
        self,
        *,
        results: Optional[Dict[str, GitHubFetchResult]] = None,
        errors: Optional[Dict[str, Exception]] = None,
    ) -> None:
        self.results = results or {}
        self.errors = errors or {}
        self.calls = []

    def _resolve(self, evidence_type, **kwargs):
        self.calls.append(
            {
                "evidence_type": evidence_type,
                **kwargs,
            }
        )

        error = self.errors.get(evidence_type)

        if error:
            raise error

        return self.results.get(
            evidence_type,
            GitHubFetchResult(),
        )

    def fetch_commits(
        self,
        reference,
        *,
        etag=None,
        since=None,
    ):
        return self._resolve(
            "commit",
            reference=reference,
            etag=etag,
            since=since,
        )

    def fetch_pull_requests(
        self,
        reference,
        *,
        etag=None,
    ):
        return self._resolve(
            "pull_request",
            reference=reference,
            etag=etag,
        )

    def fetch_releases(
        self,
        reference,
        *,
        etag=None,
    ):
        return self._resolve(
            "release",
            reference=reference,
            etag=etag,
        )

    def fetch_workflow_runs(
        self,
        reference,
        *,
        etag=None,
    ):
        return self._resolve(
            "workflow_run",
            reference=reference,
            etag=etag,
        )


def _commit_payload(sha: str):
    return {
        "sha": sha,
        "html_url": (
            "https://github.com/owner/repo/commit/"
            f"{sha}"
        ),
        "commit": {
            "message": "Add execution evidence service",
            "author": {
                "date": "2026-07-13T10:00:00Z",
            },
        },
    }


def _pull_request_payload(number: int):
    return {
        "number": number,
        "title": "Add execution evidence service",
        "html_url": (
            "https://github.com/owner/repo/pull/"
            f"{number}"
        ),
        "created_at": "2026-07-13T10:00:00Z",
        "state": "open",
    }


def _release_payload(release_id: int):
    return {
        "id": release_id,
        "tag_name": "v2.3.0",
        "html_url": (
            "https://github.com/owner/repo/releases/"
            f"{release_id}"
        ),
        "created_at": "2026-07-13T10:00:00Z",
    }


def _workflow_payload(run_id: int):
    return {
        "id": run_id,
        "name": "Backend tests",
        "html_url": (
            "https://github.com/owner/repo/actions/runs/"
            f"{run_id}"
        ),
        "created_at": "2026-07-13T10:00:00Z",
        "status": "completed",
        "conclusion": "success",
    }


def test_service_fetches_normalizes_and_merges_all_evidence_types():
    client = FakeGitHubClient(
        results={
            "commit": GitHubFetchResult(
                payloads=[_commit_payload("abc123")]
            ),
            "pull_request": GitHubFetchResult(
                payloads=[_pull_request_payload(42)]
            ),
            "release": GitHubFetchResult(
                payloads=[_release_payload(9001)]
            ),
            "workflow_run": GitHubFetchResult(
                payloads=[_workflow_payload(7001)]
            ),
        }
    )

    service = GitHubExecutionEvidenceService(
        client=client
    )

    result = service.sync_repository(
        repository_url=REPOSITORY_URL,
        existing_evidence=[],
        previous_state=None,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "succeeded"
    assert len(result.evidence) == 4
    assert {
        item.evidence_type
        for item in result.evidence
    } == {
        "commit",
        "pull_request",
        "release",
        "workflow_run",
    }
    assert result.sync_state.latest_commit_sha == "abc123"
    assert result.sync_state.status == "succeeded"
    assert result.failed_types == []


def test_service_preserves_successful_batches_when_one_fetch_fails():
    client = FakeGitHubClient(
        results={
            "commit": GitHubFetchResult(
                payloads=[_commit_payload("abc123")]
            ),
            "release": GitHubFetchResult(
                payloads=[_release_payload(9001)]
            ),
        },
        errors={
            "pull_request": GitHubClientError(
                "GitHub returned 403.",
                status_code=403,
            ),
        },
    )

    service = GitHubExecutionEvidenceService(
        client=client
    )

    result = service.sync_repository(
        repository_url=REPOSITORY_URL,
        existing_evidence=[],
        previous_state=None,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "partially_succeeded"
    assert {
        item.evidence_type
        for item in result.evidence
    } == {
        "commit",
        "release",
    }
    assert result.failed_types == ["pull_request"]
    assert result.sync_state.status == "failed"
    assert result.sync_state.latest_commit_sha == "abc123"


def test_service_treats_not_modified_response_as_success():
    client = FakeGitHubClient(
        results={
            "commit": GitHubFetchResult(
                not_modified=True,
                etag='"commit-etag"',
            ),
            "pull_request": GitHubFetchResult(
                not_modified=True,
            ),
            "release": GitHubFetchResult(
                not_modified=True,
            ),
            "workflow_run": GitHubFetchResult(
                not_modified=True,
            ),
        }
    )

    existing = ExecutionEvidenceItem(
        repository_full_name=(
            "omkarhundekari/"
            "semantic-recommendation-system"
        ),
        evidence_type="commit",
        external_id="oldsha",
        title="Existing evidence",
        url="https://github.com/owner/repo/commit/oldsha",
        occurred_at=OBSERVED_AT,
        first_seen_at=OBSERVED_AT,
        last_seen_at=OBSERVED_AT,
    )

    previous_state = RepositorySyncState(
        repository_key=REPOSITORY_KEY,
        status="succeeded",
        latest_commit_sha="oldsha",
    )

    service = GitHubExecutionEvidenceService(
        client=client
    )

    result = service.sync_repository(
        repository_url=REPOSITORY_URL,
        existing_evidence=[existing],
        previous_state=previous_state,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "succeeded"
    assert result.evidence == [existing]
    assert result.sync_state.latest_commit_sha == "oldsha"


def test_service_forwards_etags_and_since_cursor():
    client = FakeGitHubClient()

    service = GitHubExecutionEvidenceService(
        client=client
    )

    service.sync_repository(
        repository_url=REPOSITORY_URL,
        existing_evidence=[],
        previous_state=None,
        observed_at=OBSERVED_AT,
        etags={
            "commit": '"commit-etag"',
            "pull_request": '"pr-etag"',
            "release": '"release-etag"',
            "workflow_run": '"workflow-etag"',
        },
        since="2026-07-01T00:00:00Z",
    )

    calls = {
        call["evidence_type"]: call
        for call in client.calls
    }

    assert calls["commit"]["etag"] == '"commit-etag"'
    assert (
        calls["commit"]["since"]
        == "2026-07-01T00:00:00Z"
    )
    assert calls["pull_request"]["etag"] == '"pr-etag"'
    assert calls["release"]["etag"] == '"release-etag"'
    assert (
        calls["workflow_run"]["etag"]
        == '"workflow-etag"'
    )


def test_service_turns_normalization_failure_into_batch_failure():
    client = FakeGitHubClient(
        results={
            "commit": GitHubFetchResult(
                payloads=[
                    {
                        "sha": "",
                        "html_url": (
                            "https://github.com/owner/repo/commit/a"
                        ),
                        "commit": {
                            "message": "Invalid commit",
                            "author": {
                                "date": (
                                    "2026-07-13T10:00:00Z"
                                ),
                            },
                        },
                    }
                ]
            ),
        }
    )

    service = GitHubExecutionEvidenceService(
        client=client
    )

    result = service.sync_repository(
        repository_url=REPOSITORY_URL,
        existing_evidence=[],
        previous_state=None,
        observed_at=OBSERVED_AT,
    )

    assert result.status == "partially_succeeded"
    assert result.failed_types == ["commit"]
    assert "sha" in result.errors["commit"]


def test_service_rejects_mismatched_repository_state():
    client = FakeGitHubClient()

    service = GitHubExecutionEvidenceService(
        client=client
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        service.sync_repository(
            repository_url=REPOSITORY_URL,
            existing_evidence=[],
            previous_state=RepositorySyncState(
                repository_key="github:other/repository",
            ),
            observed_at=OBSERVED_AT,
        )
