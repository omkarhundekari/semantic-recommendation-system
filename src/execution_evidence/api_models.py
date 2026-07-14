from __future__ import annotations

from typing import Annotated, Optional

from pydantic import (
    BaseModel,
    Field,
    StringConstraints,
    model_validator,
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


class AttributionIdentityRequest(BaseModel):
    project_direction_id: Optional[
        NonBlankIdentifier
    ] = None
    project_id: Optional[
        NonBlankIdentifier
    ] = None
    roadmap_snapshot_id: Optional[
        NonBlankIdentifier
    ] = None

    @model_validator(mode="after")
    def validate_roadmap_identity(
        self,
    ) -> "AttributionIdentityRequest":
        has_project_id = self.project_id is not None
        has_snapshot_id = (
            self.roadmap_snapshot_id is not None
        )

        if has_project_id != has_snapshot_id:
            raise ValueError(
                "project_id and roadmap_snapshot_id "
                "must be supplied together."
            )

        if (
            self.project_direction_id is None
            and not has_project_id
        ):
            raise ValueError(
                "A durable roadmap identity or "
                "project_direction_id is required."
            )

        return self


class EvidenceAttributionAttachRequest(
    AttributionIdentityRequest
):
    repository_key: NonBlankIdentifier
    evidence_key: NonBlankIdentifier
    roadmap_node_id: NonBlankIdentifier
    rationale: str = ""
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )


class EvidenceAttributionDetachRequest(
    AttributionIdentityRequest
):
    repository_key: NonBlankIdentifier
    evidence_key: NonBlankIdentifier
    roadmap_node_id: NonBlankIdentifier
    expected_revision: Optional[int] = Field(
        default=None,
        ge=-1,
    )


class EvidenceAttributionListQuery(
    AttributionIdentityRequest
):
    repository_key: NonBlankIdentifier
    roadmap_node_id: Optional[
        NonBlankIdentifier
    ] = None


class EvidenceAttributionDetachResponse(BaseModel):
    removed: bool
