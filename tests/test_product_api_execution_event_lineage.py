from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_projection import (
    build_execution_event_lineage_projection,
)
from execution_evidence.execution_event_projection_service import (
    ExecutionEventProjectionUnsupportedStoreError,
)
from execution_evidence.execution_event_store import (
    StoredExecutionEvent,
)
from product_api import (
    app,
    get_execution_event_projection_service,
)


BASE_TIME = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=timezone.utc,
)


def _event_id(number: int) -> str:
    return (
        "evt_00000000-0000-4000-8000-"
        f"{number:012x}"
    )


def _record(
    number: int,
    *,
    sequence: int,
    supersedes: int | None = None,
) -> StoredExecutionEvent:
    return StoredExecutionEvent(
        store_sequence=sequence,
        event=ExecutionEvent(
            execution_event_id=(
                _event_id(number)
            ),
            supersedes_execution_event_id=(
                _event_id(supersedes)
                if supersedes is not None
                else None
            ),
            project_id="project-test",
            event_type="test.execution.event",
            occurred_at=BASE_TIME,
            recorded_at=BASE_TIME,
            source_provider="test",
            client_idempotency_key=(
                f"client-{number}"
            ),
            ingestion_method="system",
            payload={
                "number": number,
            },
        ),
    )


class RecordingProjectionService:
    def __init__(
        self,
        projection,
    ) -> None:
        self.projection = projection
        self.calls = []

    def project_lineage(
        self,
        project_id: str,
        *,
        limit: int | None = None,
    ):
        self.calls.append(
            {
                "project_id": project_id,
                "limit": limit,
            }
        )

        return self.projection


class FailingProjectionService:
    def __init__(self, error: Exception):
        self.error = error

    def project_lineage(
        self,
        project_id: str,
        *,
        limit: int | None = None,
    ):
        raise self.error


def _client_for(service):
    app.dependency_overrides[
        get_execution_event_projection_service
    ] = lambda: service

    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def test_lineage_endpoint_returns_ordered_projection():
    original = _record(
        1,
        sequence=1,
    )
    first_correction = _record(
        2,
        sequence=2,
        supersedes=1,
    )
    authoritative_correction = _record(
        3,
        sequence=3,
        supersedes=1,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                authoritative_correction,
                original,
                first_correction,
            ],
        )
    )
    service = RecordingProjectionService(
        projection
    )

    try:
        with _client_for(service) as client:
            response = client.get(
                (
                    "/v1/projects/project-test/"
                    "execution-evidence/events/"
                    "lineage"
                ),
                params={
                    "limit": 50,
                },
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()

    assert service.calls == [
        {
            "project_id": "project-test",
            "limit": 50,
        }
    ]

    assert body["project_id"] == "project-test"
    assert [
        record["store_sequence"]
        for record in body["ordered_records"]
    ] == [1, 2, 3]

    assert body["authoritative_event_ids"] == [
        original.event.execution_event_id,
        authoritative_correction
        .event.execution_event_id,
    ]

    assert body["terminal_event_ids"] == [
        authoritative_correction
        .event.execution_event_id,
    ]

    assert body["has_conflicts"] is True
    assert body["conflicts"] == [
        {
            "predecessor_event_id": (
                original.event.execution_event_id
            ),
            "successor_event_ids": [
                first_correction
                .event.execution_event_id,
                authoritative_correction
                .event.execution_event_id,
            ],
            (
                "authoritative_successor_event_id"
            ): (
                authoritative_correction
                .event.execution_event_id
            ),
        }
    ]


def test_lineage_endpoint_uses_default_limit():
    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [],
        )
    )
    service = RecordingProjectionService(
        projection
    )

    try:
        with _client_for(service) as client:
            response = client.get(
                (
                    "/v1/projects/project-test/"
                    "execution-evidence/events/"
                    "lineage"
                )
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert service.calls == [
        {
            "project_id": "project-test",
            "limit": 1000,
        }
    ]


def test_lineage_endpoint_rejects_invalid_limit():
    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [],
        )
    )
    service = RecordingProjectionService(
        projection
    )

    try:
        with _client_for(service) as client:
            response = client.get(
                (
                    "/v1/projects/project-test/"
                    "execution-evidence/events/"
                    "lineage"
                ),
                params={
                    "limit": 1001,
                },
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == (
            "Execution event projection limit "
            "must be between 1 and 1000."
        )
    )
    assert service.calls == []


def test_lineage_endpoint_returns_503_for_unsupported_store():
    service = FailingProjectionService(
        ExecutionEventProjectionUnsupportedStoreError(
            "The configured execution event store "
            "does not expose authoritative "
            "storage order."
        )
    )

    try:
        with _client_for(service) as client:
            response = client.get(
                (
                    "/v1/projects/project-test/"
                    "execution-evidence/events/"
                    "lineage"
                )
            )
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert (
        "authoritative storage order"
        in response.json()["detail"]
    )
