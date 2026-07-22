from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from execution_evidence.execution_event_payload import (
    EXECUTION_EVENT_PAYLOAD_REGISTRY,
    ExecutionEventPayload,
    validate_execution_event_payload,
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
    supersedes_execution_event_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
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
    payload: Union[
        Dict[str, Any],
        ExecutionEventPayload,
    ] = Field(default_factory=dict)

    @field_validator(
        "supersedes_execution_event_id",
    )
    @classmethod
    def validate_superseded_event_id(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        prefix = "evt_"
        if not value.startswith(prefix):
            raise ValueError(
                "Superseded execution event IDs must "
                "start with 'evt_'."
            )

        raw_uuid = value[len(prefix):]

        try:
            parsed_uuid = UUID(raw_uuid)
        except ValueError as error:
            raise ValueError(
                "Superseded execution event IDs must "
                "contain a valid UUID."
            ) from error

        if (
            parsed_uuid.version != 4
            or str(parsed_uuid) != raw_uuid
        ):
            raise ValueError(
                "Superseded execution event IDs must "
                "contain a canonical UUID4."
            )

        return value

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
    def reject_self_supersession(
        self,
    ) -> "ExecutionEvent":
        if (
            self.supersedes_execution_event_id
            == self.execution_event_id
        ):
            raise ValueError(
                "An execution event cannot supersede itself."
            )

        return self

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

    @model_validator(mode="after")
    def validate_payload_contract(
        self,
    ) -> "ExecutionEvent":
        if (
            self.event_type
            not in EXECUTION_EVENT_PAYLOAD_REGISTRY
        ):
            return self

        try:
            validate_execution_event_payload(
                event_type=self.event_type,
                payload=self.payload,
            )
        except TypeError as error:
            raise ValueError(str(error)) from error

        return self

    def immutable_fingerprint(self) -> str:
        event_data = self.model_dump(
            mode="json",
            exclude={
                "execution_event_id",
                "recorded_at",
                "payload",
            },
        )

        if isinstance(
            self.payload,
            ExecutionEventPayload,
        ):
            event_data["payload"] = (
                self.payload.model_dump(
                    mode="json"
                )
            )
        else:
            event_data["payload"] = self.payload

        canonical = json.dumps(
            event_data,
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
