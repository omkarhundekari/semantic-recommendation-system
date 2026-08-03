from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class GitHubWebhookAuthenticatedSource(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    github_webhook_credential_id: str = Field(
        min_length=1
    )
    github_webhook_credential_authority_id: str = (
        Field(min_length=1)
    )
    webhook_endpoint_id: str = Field(min_length=1)
    repository_id: str = Field(min_length=1)
