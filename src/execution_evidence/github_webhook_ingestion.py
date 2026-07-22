from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from execution_evidence.execution_event import (
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_store import (
    ExecutionEventStore,
)
from execution_evidence.github_webhook_adapter import (
    adapt_github_webhook,
)
from execution_evidence.github_webhook_signature import (
    verify_github_webhook_signature,
)


class GitHubWebhookIngestionError(ValueError):
    pass


class GitHubWebhookMalformedJSONError(
    GitHubWebhookIngestionError
):
    pass


class GitHubWebhookPayloadShapeError(
    GitHubWebhookIngestionError
):
    pass


class GitHubWebhookIngestionService:
    def __init__(
        self,
        *,
        secret: bytes,
        event_store: ExecutionEventStore,
    ) -> None:
        if not isinstance(secret, bytes) or not secret:
            raise GitHubWebhookIngestionError(
                "GitHub webhook secret must be "
                "non-empty bytes."
            )

        if not isinstance(
            event_store,
            ExecutionEventStore,
        ):
            raise GitHubWebhookIngestionError(
                "GitHub webhook event store must "
                "implement ExecutionEventStore."
            )

        self._secret = secret
        self._event_store = event_store

    def ingest(
        self,
        *,
        project_id: str,
        event_name: str,
        delivery_id: str,
        signature_header: Optional[str],
        raw_body: bytes,
        recorded_at: datetime,
    ) -> ExecutionEventAppendResult:
        verify_github_webhook_signature(
            secret=self._secret,
            raw_body=raw_body,
            signature_header=signature_header,
        )

        try:
            payload = json.loads(raw_body)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ) as error:
            raise GitHubWebhookMalformedJSONError(
                "GitHub webhook body must contain "
                "valid UTF-8 JSON."
            ) from error

        if not isinstance(payload, dict):
            raise GitHubWebhookPayloadShapeError(
                "GitHub webhook JSON payload must "
                "be an object."
            )

        event = adapt_github_webhook(
            project_id=project_id,
            event_name=event_name,
            delivery_id=delivery_id,
            recorded_at=recorded_at,
            payload=payload,
        )

        return self._event_store.append(event)
