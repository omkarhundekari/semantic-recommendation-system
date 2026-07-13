from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional

from execution_evidence.github_client import (
    GitHubClientError,
    GitHubExecutionEvidenceClient,
    GitHubFetchResult,
)
from execution_evidence.github_normalization import (
    GitHubPayloadError,
    normalize_many,
)
from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    EvidenceType,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.sync import (
    GitHubSyncBatch,
    GitHubSyncResult,
    apply_github_sync,
)


class GitHubExecutionEvidenceService:
    def __init__(
        self,
        *,
        client: GitHubExecutionEvidenceClient,
    ) -> None:
        self._client = client

    def sync_repository(
        self,
        *,
        repository_url: str,
        existing_evidence: Iterable[ExecutionEvidenceItem],
        previous_state: Optional[RepositorySyncState],
        observed_at: datetime,
        etags: Optional[Dict[EvidenceType, str]] = None,
        since: Optional[str] = None,
    ) -> GitHubSyncResult:
        reference = parse_github_repository_url(repository_url)
        repository_key = reference.repository_key

        state = previous_state or RepositorySyncState(
            repository_key=repository_key,
        )

        if state.repository_key != repository_key:
            raise ValueError(
                "Repository sync state does not match the requested repository."
            )

        etag_map = etags or {}
        batches = []

        fetchers = {
            "commit": lambda: self._client.fetch_commits(
                reference,
                etag=etag_map.get("commit"),
                since=since,
            ),
            "pull_request": lambda: self._client.fetch_pull_requests(
                reference,
                etag=etag_map.get("pull_request"),
            ),
            "release": lambda: self._client.fetch_releases(
                reference,
                etag=etag_map.get("release"),
            ),
            "workflow_run": lambda: self._client.fetch_workflow_runs(
                reference,
                etag=etag_map.get("workflow_run"),
            ),
        }

        latest_commit_sha = state.latest_commit_sha

        for evidence_type, fetcher in fetchers.items():
            try:
                fetch_result = fetcher()
                batch = self._build_batch(
                    repository_full_name=reference.full_name,
                    evidence_type=evidence_type,
                    fetch_result=fetch_result,
                    observed_at=observed_at,
                )
            except (
                GitHubClientError,
                GitHubPayloadError,
                ValueError,
            ) as error:
                batch = GitHubSyncBatch(
                    evidence_type=evidence_type,
                    status="failed",
                    error_message=str(error),
                )

            batches.append(batch)

            if evidence_type == "commit" and batch.status == "succeeded":
                if batch.items:
                    latest_commit_sha = batch.items[0].external_id

        return apply_github_sync(
            repository_key=repository_key,
            existing_evidence=existing_evidence,
            previous_state=state,
            batches=batches,
            attempted_at=observed_at,
            latest_commit_sha=latest_commit_sha,
            cursor=since,
        )

    @staticmethod
    def _build_batch(
        *,
        repository_full_name: str,
        evidence_type: EvidenceType,
        fetch_result: GitHubFetchResult,
        observed_at: datetime,
    ) -> GitHubSyncBatch:
        if fetch_result.not_modified:
            return GitHubSyncBatch(
                evidence_type=evidence_type,
                status="succeeded",
                items=[],
            )

        items = normalize_many(
            repository_full_name=repository_full_name,
            evidence_type=evidence_type,
            payloads=fetch_result.payloads,
            observed_at=observed_at,
        )

        return GitHubSyncBatch(
            evidence_type=evidence_type,
            status="succeeded",
            items=items,
        )
