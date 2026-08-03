from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GitHubSourceRoute(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    github_source_binding_id: str = Field(
        min_length=1
    )
    repository_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
