from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


ExecutionEventVisibility = Literal[
    "private",
    "project",
    "shareable",
    "public",
]

ExecutionEventIngestionMethod = Literal[
    "manual",
    "api",
    "webhook",
    "import",
    "system",
]


class ExecutionEvent(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    execution_event_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)

    occurred_at: datetime
    recorded_at: datetime

    actor_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    ingested_by_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )

    source_provider: str = Field(min_length=1)
    source_account_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    external_resource_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    external_entity_type: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    external_entity_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )

    provider_idempotency_key: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    client_idempotency_key: Optional[str] = Field(
        default=None,
        min_length=1,
    )

    ingestion_method: ExecutionEventIngestionMethod
    source_payload_hash: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    verified_at: Optional[datetime] = None

    visibility: ExecutionEventVisibility = "private"
    payload: Dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator(
        "occurred_at",
        "recorded_at",
        "verified_at",
    )
    @classmethod
    def require_timezone(
        cls,
        value: Optional[datetime],
    ) -> Optional[datetime]:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Execution event timestamps must "
                "be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_idempotency(
        self,
    ) -> "ExecutionEvent":
        if (
            self.provider_idempotency_key is None
            and self.client_idempotency_key is None
        ):
            raise ValueError(
                "Execution events require a provider "
                "or client idempotency key."
            )

        if (
            self.ingestion_method == "webhook"
            and self.provider_idempotency_key is None
        ):
            raise ValueError(
                "Webhook execution events require a "
                "provider idempotency key."
            )

        return self

    def immutable_fingerprint(self) -> str:
        payload = self.model_dump(
            mode="json",
            exclude={
                "execution_event_id",
                "recorded_at",
            },
        )
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()


class ExecutionEventAppendResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    event: ExecutionEvent
    created: bool


def create_execution_event_id() -> str:
    return f"evt_{uuid4()}"
