from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CurrentActorResolution(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    principal_id: str = Field(min_length=1)
    identity_link_id: str = Field(min_length=1)
    execution_actor_namespace_id: str = Field(
        min_length=1
    )
    issuer: str = Field(min_length=1)
    subject: str = Field(min_length=1)
