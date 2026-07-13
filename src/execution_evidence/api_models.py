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
