from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field, model_validator


EvidenceType = Literal[
    "commit",
    "pull_request",
    "release",
    "workflow_run",
]

AttributionSource = Literal[
    "deterministic",
    "semantic",
    "manual",
]

AttributionStatus = Literal[
    "suggested",
    "accepted",
    "rejected",
]


class GitHubRepositoryReference(BaseModel):
    provider: Literal["github"] = "github"
    owner: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    canonical_url: str = Field(min_length=1)

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repository}"

    @property
    def repository_key(self) -> str:
        return f"{self.provider}:{self.full_name.lower()}"


class ExecutionEvidenceItem(BaseModel):
    provider: Literal["github"] = "github"
    repository_full_name: str = Field(min_length=3)
    evidence_type: EvidenceType
    external_id: str = Field(min_length=1)

    title: str = Field(min_length=1)
    description: str = ""
    url: str = Field(min_length=1)
    occurred_at: datetime

    metadata: Dict[str, Any] = Field(default_factory=dict)
    first_seen_at: datetime
    last_seen_at: datetime

    @property
    def evidence_key(self) -> str:
        return ":".join(
            [
                self.provider,
                self.repository_full_name.lower(),
                self.evidence_type,
                self.external_id,
            ]
        )


class RoadmapAttributionContext(BaseModel):
    roadmap_hash: str = Field(
        pattern=r"^[0-9a-f]{64}$",
    )
    roadmap_stage_hash: str = Field(
        pattern=r"^[0-9a-f]{64}$",
    )
    roadmap_node_id: str = Field(min_length=1)
    snapshot_version: int = Field(ge=1)
    canonicalization_version: int = Field(ge=1)


class EvidenceAttribution(BaseModel):
    attribution_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    project_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    roadmap_snapshot_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    project_direction_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    evidence_key: str = Field(min_length=1)
    roadmap_node_id: str = Field(min_length=1)
    source: AttributionSource
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = ""
    status: AttributionStatus = "suggested"
    decided_at: Optional[datetime] = None
    roadmap_context: Optional[
        RoadmapAttributionContext
    ] = None

    @model_validator(mode="after")
    def validate_identity(
        self,
    ) -> "EvidenceAttribution":
        if (
            self.roadmap_context is not None
            and self.roadmap_context.roadmap_node_id
            != self.roadmap_node_id
        ):
            raise ValueError(
                "Roadmap attribution context must match "
                "roadmap_node_id."
            )

        if (
            self.project_direction_id is not None
            and self.attribution_id is None
        ):
            raise ValueError(
                "Project-scoped attribution requires "
                "attribution_id."
            )

        if (
            self.project_direction_id is not None
            and self.roadmap_context is None
        ):
            raise ValueError(
                "Project-scoped attribution requires "
                "trusted roadmap context."
            )

        if (
            self.attribution_id is not None
            and self.project_direction_id is None
        ):
            raise ValueError(
                "Attribution ID requires "
                "project_direction_id."
            )

        return self

    @property
    def attribution_identity(
        self,
    ) -> tuple[Optional[str], str, str]:
        return (
            self.project_direction_id,
            self.evidence_key,
            self.roadmap_node_id,
        )

    @property
    def attribution_key(self) -> str:
        return f"{self.evidence_key}:{self.roadmap_node_id}"


class RepositorySyncState(BaseModel):
    repository_key: str = Field(min_length=1)
    status: Literal[
        "never_synced",
        "syncing",
        "succeeded",
        "failed",
    ] = "never_synced"

    latest_commit_sha: Optional[str] = None
    cursor: Optional[str] = None
    last_attempted_at: Optional[datetime] = None
    last_succeeded_at: Optional[datetime] = None
    error_message: Optional[str] = None
