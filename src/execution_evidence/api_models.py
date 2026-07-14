from __future__ import annotations

from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
)


NonBlankIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
    ),
]


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
    project_direction_id: NonBlankIdentifier
    repository_key: NonBlankIdentifier
    evidence_key: NonBlankIdentifier
    roadmap_node_id: NonBlankIdentifier
    rationale: str = ""
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )


class EvidenceAttributionDetachRequest(BaseModel):
    project_direction_id: NonBlankIdentifier
    repository_key: NonBlankIdentifier
    evidence_key: NonBlankIdentifier
    roadmap_node_id: NonBlankIdentifier
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )



class EvidenceAttributionListQuery(BaseModel):
    repository_key: NonBlankIdentifier
    project_direction_id: NonBlankIdentifier
    roadmap_node_id: Optional[
        NonBlankIdentifier
    ] = None


class EvidenceAttributionDetachResponse(BaseModel):
    removed: bool
