from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import RepositorySyncState
from execution_evidence.service import (
    GitHubExecutionEvidenceService,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.store import (
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)
from execution_evidence.sync import GitHubSyncResult


class StatefulGitHubSyncResult(BaseModel):
    sync: GitHubSyncResult
    stored: StoredRepositoryEvidence
    created: bool


class StatefulGitHubSyncCoordinator:
    def __init__(
        self,
        *,
        service: GitHubExecutionEvidenceService,
        store: RepositoryEvidenceStore,
    ) -> None:
        self._service = service
        self._store = store

    def sync_repository(
        self,
        *,
        repository_url: str,
        observed_at: datetime,
        since: Optional[str] = None,
    ) -> StatefulGitHubSyncResult:
        reference = parse_github_repository_url(
            repository_url
        )
        repository_key = reference.repository_key

        existing = self._store.load(repository_key)
        created = existing is None

        if existing is None:
            existing = StoredRepositoryEvidence(
                repository=reference,
                evidence=[],
                sync_state=RepositorySyncState(
                    repository_key=repository_key,
                ),
                sync_snapshot=GitHubRepositorySyncSnapshot(
                    repository_key=repository_key,
                ),
                saved_at=observed_at,
            )

        sync_result = self._service.sync_repository(
            repository_url=reference.canonical_url,
            existing_evidence=existing.evidence,
            previous_state=existing.sync_state,
            previous_snapshot=existing.sync_snapshot,
            observed_at=observed_at,
            since=since,
        )

        updated_record = existing.model_copy(
            update={
                "evidence": sync_result.evidence,
                "sync_state": sync_result.sync_state,
                "sync_snapshot": (
                    sync_result.sync_snapshot
                    or existing.sync_snapshot
                ),
                "saved_at": observed_at,
            },
            deep=True,
        )

        saved = self._store.save(
            updated_record,
            expected_revision=(
                -1
                if created
                else existing.revision
            ),
        )

        return StatefulGitHubSyncResult(
            sync=sync_result,
            stored=saved,
            created=created,
        )
