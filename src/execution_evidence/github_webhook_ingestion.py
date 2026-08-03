from __future__ import annotations

import json
from datetime import datetime
from typing import Callable, Optional

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


class GitHubWebhookRepositoryIdentityError(
    GitHubWebhookIngestionError
):
    pass


class GitHubWebhookProjectBindingMismatchError(
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
        secret: bytes,
        routing_service: GitHubSourceRoutingService,
        event_store_factory: Callable[
            [str],
            ExecutionEventStore,
        ],
    ) -> None:
        if not isinstance(secret, bytes) or not secret:
            raise GitHubWebhookIngestionError(
                "GitHub webhook secret must be "
                "non-empty bytes."
            )

        resolve_route = getattr(
            routing_service,
            "resolve",
            None,
        )

        if not callable(resolve_route):
            raise GitHubWebhookIngestionError(
                "GitHub webhook routing service must "
                "provide trusted source resolution."
            )

        if not callable(event_store_factory):
            raise GitHubWebhookIngestionError(
                "GitHub webhook event store factory "
                "must be callable."
            )

        self._secret = secret
        self._routing_service = routing_service
        self._event_store_factory = (
            event_store_factory
        )

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

        repository_id = (
            self._extract_repository_id(payload)
        )

        try:
            route = self._routing_service.resolve(
                repository_id
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

        if project_id != route.project_id:
            raise (
                GitHubWebhookProjectBindingMismatchError(
                    "GitHub webhook project does not "
                    "match the trusted repository "
                    "binding."
                )
            )

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

    @staticmethod
    def _extract_repository_id(
        payload: dict,
    ) -> str:
        repository = payload.get("repository")

        if not isinstance(repository, dict):
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook repository must be "
                "an object."
            )

        repository_id = repository.get("id")

        if (
            not isinstance(repository_id, int)
            or isinstance(repository_id, bool)
            or repository_id < 1
        ):
            raise GitHubWebhookRepositoryIdentityError(
                "GitHub webhook repository ID must "
                "be a positive integer."
            )

        return str(repository_id)
