from __future__ import annotations

from datetime import datetime
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field

from execution_evidence.github_client import GitHubRateLimit
from execution_evidence.models import EvidenceType


SourceSyncStatus = Literal[
    "never_synced",
    "succeeded",
    "not_modified",
    "failed",
]


class GitHubSourceSyncSnapshot(BaseModel):
    status: SourceSyncStatus = "never_synced"
    etag: Optional[str] = None
    pages_fetched: int = Field(default=0, ge=0)
    last_attempted_at: Optional[datetime] = None
    last_succeeded_at: Optional[datetime] = None
    error_message: Optional[str] = None
    rate_limit: GitHubRateLimit = Field(
        default_factory=GitHubRateLimit
    )


class GitHubRepositorySyncSnapshot(BaseModel):
    repository_key: str = Field(min_length=1)
    sources: Dict[
        EvidenceType,
        GitHubSourceSyncSnapshot,
    ] = Field(default_factory=dict)

    def etags(self) -> Dict[EvidenceType, str]:
        return {
            evidence_type: source.etag
            for evidence_type, source in self.sources.items()
            if source.etag
        }


class GitHubSourceSyncObservation(BaseModel):
    evidence_type: EvidenceType
    status: Literal[
        "succeeded",
        "not_modified",
        "failed",
    ]
    observed_at: datetime
    etag: Optional[str] = None
    pages_fetched: int = Field(default=0, ge=0)
    error_message: Optional[str] = None
    rate_limit: GitHubRateLimit = Field(
        default_factory=GitHubRateLimit
    )

    def model_post_init(self, __context) -> None:
        if self.status == "failed" and not self.error_message:
            raise ValueError(
                "Failed source observations require an error message."
            )

        if self.status != "failed" and self.error_message:
            raise ValueError(
                "Successful source observations cannot include an error."
            )


def update_github_sync_snapshot(
    *,
    previous: GitHubRepositorySyncSnapshot,
    observations: list[GitHubSourceSyncObservation],
) -> GitHubRepositorySyncSnapshot:
    updated_sources = dict(previous.sources)

    for observation in observations:
        current = updated_sources.get(
            observation.evidence_type,
            GitHubSourceSyncSnapshot(),
        )

        if observation.status == "failed":
            updated_sources[observation.evidence_type] = (
                current.model_copy(
                    update={
                        "status": "failed",
                        "last_attempted_at": observation.observed_at,
                        "error_message": observation.error_message,
                        "pages_fetched": observation.pages_fetched,
                        "rate_limit": observation.rate_limit,
                    }
                )
            )
            continue

        updated_sources[observation.evidence_type] = (
            current.model_copy(
                update={
                    "status": observation.status,
                    "etag": observation.etag or current.etag,
                    "pages_fetched": observation.pages_fetched,
                    "last_attempted_at": observation.observed_at,
                    "last_succeeded_at": observation.observed_at,
                    "error_message": None,
                    "rate_limit": observation.rate_limit,
                }
            )
        )

    return previous.model_copy(
        update={"sources": updated_sources}
    )
