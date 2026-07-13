from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RepositoryEvidenceSyncRequest(BaseModel):
    repository_url: str = Field(
        min_length=1,
        description="Public github.com repository URL.",
    )
    since: Optional[str] = Field(
        default=None,
        description=(
            "Optional GitHub-compatible ISO-8601 timestamp "
            "used to constrain commit ingestion."
        ),
    )


class EvidenceAttributionAttachRequest(BaseModel):
    repository_key: str = Field(min_length=1)
    evidence_key: str = Field(min_length=1)
    roadmap_node_id: str = Field(min_length=1)
    rationale: str = ""
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )


class EvidenceAttributionDetachRequest(BaseModel):
    repository_key: str = Field(min_length=1)
    evidence_key: str = Field(min_length=1)
    roadmap_node_id: str = Field(min_length=1)
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )


class EvidenceAttributionDetachResponse(BaseModel):
    removed: bool
