from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, Field

from execution_evidence.merge import merge_execution_evidence
from execution_evidence.models import (
    EvidenceType,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)


BatchStatus = Literal["succeeded", "failed"]


class GitHubSyncBatch(BaseModel):
    evidence_type: EvidenceType
    status: BatchStatus
    items: List[ExecutionEvidenceItem] = Field(default_factory=list)
    error_message: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if self.status == "failed" and not self.error_message:
            raise ValueError(
                "Failed sync batches must include an error message."
            )

        if self.status == "failed" and self.items:
            raise ValueError(
                "Failed sync batches cannot include evidence items."
            )


class GitHubSyncResult(BaseModel):
    repository_key: str
    status: Literal[
        "succeeded",
        "partially_succeeded",
        "failed",
    ]
    evidence: List[ExecutionEvidenceItem]
    sync_state: RepositorySyncState
    sync_snapshot: Optional[
        GitHubRepositorySyncSnapshot
    ] = None
    synced_counts: Dict[EvidenceType, int]
    failed_types: List[EvidenceType]
    errors: Dict[EvidenceType, str]


def apply_github_sync(
    *,
    repository_key: str,
    existing_evidence: Iterable[ExecutionEvidenceItem],
    previous_state: RepositorySyncState,
    batches: Iterable[GitHubSyncBatch],
    attempted_at: datetime,
    latest_commit_sha: Optional[str] = None,
    cursor: Optional[str] = None,
    sync_snapshot: Optional[
        GitHubRepositorySyncSnapshot
    ] = None,
) -> GitHubSyncResult:
    batch_list = list(batches)

    successful_batches = [
        batch
        for batch in batch_list
        if batch.status == "succeeded"
    ]
    failed_batches = [
        batch
        for batch in batch_list
        if batch.status == "failed"
    ]

    incoming_items = [
        item
        for batch in successful_batches
        for item in batch.items
    ]

    merged_evidence = merge_execution_evidence(
        existing=existing_evidence,
        incoming=incoming_items,
    )

    if successful_batches and failed_batches:
        overall_status = "partially_succeeded"
        sync_state_status = "failed"
    elif failed_batches:
        overall_status = "failed"
        sync_state_status = "failed"
    else:
        overall_status = "succeeded"
        sync_state_status = "succeeded"

    errors = {
        batch.evidence_type: batch.error_message or ""
        for batch in failed_batches
    }

    synced_counts = {
        batch.evidence_type: len(batch.items)
        for batch in successful_batches
    }

    state_update = {
        "status": sync_state_status,
        "last_attempted_at": attempted_at,
        "error_message": (
            "; ".join(
                f"{evidence_type}: {message}"
                for evidence_type, message in errors.items()
            )
            or None
        ),
    }

    if successful_batches:
        state_update.update(
            {
                "last_succeeded_at": attempted_at,
                "latest_commit_sha": (
                    latest_commit_sha
                    if latest_commit_sha is not None
                    else previous_state.latest_commit_sha
                ),
                "cursor": (
                    cursor
                    if cursor is not None
                    else previous_state.cursor
                ),
            }
        )

    sync_state = previous_state.model_copy(
        update=state_update,
    )

    return GitHubSyncResult(
        repository_key=repository_key,
        status=overall_status,
        evidence=merged_evidence,
        sync_state=sync_state,
        sync_snapshot=sync_snapshot,
        synced_counts=synced_counts,
        failed_types=[
            batch.evidence_type
            for batch in failed_batches
        ],
        errors=errors,
    )
