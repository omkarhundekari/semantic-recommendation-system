from __future__ import annotations

from datetime import datetime, timezone

import pytest

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
    ExecutionEventProjectHistoryTooLargeError,
    ExecutionEventProjectNotFoundError,
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
            execution_event_id=_event_id(number),
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
            payload={"number": number},
        ),
    )


class RecordingProjectionService:
    def __init__(self, projection) -> None:
        self.projection = projection
        self.calls = []

    def project_lineage(
        self,
        project_id: str,
    ):
        self.calls.append(project_id)
        return self.projection


class FailingProjectionService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def project_lineage(
        self,
        project_id: str,
    ):
        raise self.error


def _client_for(service):
    app.dependency_overrides[
        get_execution_event_projection_service
    ] = lambda: service
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


def test_lineage_endpoint_returns_complete_projection():
    original = _record(
        1,
        sequence=4,
    )
    first_correction = _record(
        2,
        sequence=9,
        supersedes=1,
    )
    authoritative_correction = _record(
        3,
        sequence=14,
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
                )
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    body = response.json()

    assert service.calls == ["project-test"]
    assert body["project_id"] == "project-test"
    assert (
        body["projection_through_sequence"]
        == 14
    )
    assert [
        record["store_sequence"]
        for record in body["ordered_records"]
    ] == [4, 9, 14]

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


@pytest.mark.parametrize(
    "parameter",
    [
        "limit",
        "cursor",
        "offset",
        "page",
        "page_size",
        "per_page",
        "before",
        "after",
    ],
)
def test_lineage_endpoint_rejects_each_pagination_parameter(
    parameter: str,
):
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
                params={parameter: "50"},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Execution event lineage is a complete "
        "project projection and does not support "
        f"pagination parameter '{parameter}'."
    )
    assert service.calls == []


@pytest.mark.parametrize(
    "parameter",
    [
        "from_sequence",
        "through_sequence",
    ],
)
def test_lineage_endpoint_rejects_each_unsupported_sequence_bound(
    parameter: str,
):
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
                params={parameter: "10"},
            )
    finally:
        _clear_overrides()

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Execution event lineage sequence "
        f"parameter '{parameter}' is not yet "
        "supported."
    )
    assert service.calls == []



def test_lineage_endpoint_returns_503_for_unsupported_store():
    service = FailingProjectionService(
        ExecutionEventProjectionUnsupportedStoreError(
            "The configured execution event store "
            "does not expose complete authoritative "
            "project snapshots."
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
        "complete authoritative project snapshots"
        in response.json()["detail"]
    )


def test_lineage_endpoint_returns_404_for_missing_project():
    service = FailingProjectionService(
        ExecutionEventProjectNotFoundError(
            "Execution event project does not exist."
        )
    )

    try:
        with _client_for(service) as client:
            response = client.get(
                (
                    "/v1/projects/project-missing/"
                    "execution-evidence/events/"
                    "lineage"
                )
            )
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Execution event project does not exist."
    )


def test_lineage_endpoint_returns_413_for_history_ceiling():
    service = FailingProjectionService(
        ExecutionEventProjectHistoryTooLargeError(
            "Execution event project history "
            "exceeds the synchronous lineage "
            "projection limit."
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

    assert response.status_code == 413
    assert response.json()["detail"] == (
        "Execution event project history "
        "exceeds the synchronous lineage "
        "projection limit."
    )






def test_lineage_endpoint_allows_unrelated_query_parameters():
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
                    "trace_id": "trace-test",
                    "cache_bust": "1",
                },
            )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["project_id"] == (
        "project-test"
    )
    assert response.json()[
        "projection_through_sequence"
    ] == 0
    assert service.calls == ["project-test"]
