from __future__ import annotations

import json
from datetime import datetime
from typing import Callable

from execution_evidence.execution_event import (
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_store import (
    ExecutionEventStore,
    ExecutionEventStoreError,
)
from execution_evidence.github_source_routing_service import (
    GitHubSourceRoutingNotFoundError,
    GitHubSourceRoutingService,
    GitHubSourceRoutingStoreError,
)
from execution_evidence.github_webhook_authenticated_source import (
    GitHubWebhookAuthenticatedSource,
)
from execution_evidence.github_webhook_adapter import (
    adapt_github_webhook,
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


class GitHubWebhookRoutingNotFoundError(
    GitHubWebhookIngestionError
):
    pass


class GitHubWebhookRoutingStoreError(
    RuntimeError
):
    pass


class GitHubWebhookIngestionService:
    def __init__(
        self,
        *,
        routing_service: GitHubSourceRoutingService,
        event_store_factory: Callable[
            [str],
            ExecutionEventStore,
        ],
    ) -> None:
        resolve_authenticated_source = getattr(
            routing_service,
            "resolve_authenticated_source",
            None,
        )

        if not callable(resolve_authenticated_source):
            raise GitHubWebhookIngestionError(
                "GitHub webhook routing service must "
                "provide authenticated source routing."
            )

        if not callable(event_store_factory):
            raise GitHubWebhookIngestionError(
                "GitHub webhook event store factory "
                "must be callable."
            )

        self._routing_service = routing_service
        self._event_store_factory = (
            event_store_factory
        )

    def ingest_authenticated(
        self,
        *,
        authenticated_source: GitHubWebhookAuthenticatedSource,
        event_name: str,
        delivery_id: str,
        raw_body: bytes,
        recorded_at: datetime,
    ) -> ExecutionEventAppendResult:
        if not isinstance(
            authenticated_source,
            GitHubWebhookAuthenticatedSource,
        ):
            raise TypeError(
                "GitHub webhook ingestion requires an "
                "authenticated source."
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

        try:
            route = (
                self._routing_service
                .resolve_authenticated_source(
                    authenticated_source
                )
            )
        except GitHubSourceRoutingNotFoundError as error:
            raise GitHubWebhookRoutingNotFoundError(
                "GitHub repository has no current "
                "trusted source binding."
            ) from error
        except GitHubSourceRoutingStoreError as error:
            raise GitHubWebhookRoutingStoreError(
                "Could not resolve trusted GitHub "
                "webhook routing."
            ) from error

        try:
            event_store = self._event_store_factory(
                route.workspace_id
            )
        except ExecutionEventStoreError as error:
            raise GitHubWebhookRoutingStoreError(
                "Could not construct the execution "
                "event store for the trusted workspace."
            ) from error

        if not isinstance(
            event_store,
            ExecutionEventStore,
        ):
            raise GitHubWebhookRoutingStoreError(
                "GitHub webhook event store factory "
                "returned an invalid store."
            )

        event = adapt_github_webhook(
            project_id=route.project_id,
            event_name=event_name,
            delivery_id=delivery_id,
            recorded_at=recorded_at,
            payload=payload,
        )

        return event_store.append(event)
