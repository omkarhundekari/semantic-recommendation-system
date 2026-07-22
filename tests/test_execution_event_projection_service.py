from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_projection_service import (
    ExecutionEventProjectionService,
    ExecutionEventProjectionUnsupportedStoreError,
)
from execution_evidence.execution_event_store import (
    ExecutionEventAppendResult,
    ExecutionEventStore,
    StoredExecutionEvent,
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


def _event(
    number: int,
    *,
    project_id: str = "project-test",
    supersedes: int | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        execution_event_id=_event_id(number),
        supersedes_execution_event_id=(
            _event_id(supersedes)
            if supersedes is not None
            else None
        ),
        project_id=project_id,
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
    )


class RecordingProjectionStore(
    ExecutionEventStore
):
    def __init__(
        self,
        records: List[
            StoredExecutionEvent
        ],
    ) -> None:
        self.records = records
        self.calls = []

    def append(
        self,
        event: ExecutionEvent,
    ) -> ExecutionEventAppendResult:
        raise NotImplementedError

    def load(
        self,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        raise NotImplementedError

    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        raise NotImplementedError

    def list_project_event_records(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[StoredExecutionEvent]:
        self.calls.append(
            {
                "project_id": project_id,
                "limit": limit,
            }
        )

        return list(self.records)


class UnsupportedProjectionStore(
    ExecutionEventStore
):
    def append(
        self,
        event: ExecutionEvent,
    ) -> ExecutionEventAppendResult:
        raise NotImplementedError

    def load(
        self,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        raise NotImplementedError

    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        return []


def test_service_loads_records_and_builds_projection():
    first = StoredExecutionEvent(
        store_sequence=1,
        event=_event(1),
    )
    second = StoredExecutionEvent(
        store_sequence=2,
        event=_event(
            2,
            supersedes=1,
        ),
    )

    store = RecordingProjectionStore(
        [
            second,
            first,
        ]
    )
    service = ExecutionEventProjectionService(
        store=store
    )

    projection = service.project_lineage(
        "project-test"
    )

    assert store.calls == [
        {
            "project_id": "project-test",
            "limit": 1000,
        }
    ]

    assert [
        record.store_sequence
        for record
        in projection.ordered_records
    ] == [1, 2]

    assert projection.terminal_event_ids == (
        second.event.execution_event_id,
    )


def test_service_forwards_explicit_limit():
    store = RecordingProjectionStore([])
    service = ExecutionEventProjectionService(
        store=store
    )

    service.project_lineage(
        "project-test",
        limit=25,
    )

    assert store.calls == [
        {
            "project_id": "project-test",
            "limit": 25,
        }
    ]


def test_service_uses_configured_default_limit():
    store = RecordingProjectionStore([])
    service = ExecutionEventProjectionService(
        store=store,
        default_limit=500,
    )

    service.project_lineage(
        "project-test"
    )

    assert store.calls == [
        {
            "project_id": "project-test",
            "limit": 500,
        }
    ]


def test_service_translates_unsupported_store_error():
    service = ExecutionEventProjectionService(
        store=UnsupportedProjectionStore()
    )

    with pytest.raises(
        ExecutionEventProjectionUnsupportedStoreError,
        match="authoritative storage order",
    ):
        service.project_lineage(
            "project-test"
        )


@pytest.mark.parametrize(
    "default_limit",
    [0, -1, 1001],
)
def test_service_rejects_invalid_default_limit(
    default_limit: int,
):
    with pytest.raises(
        ValueError,
        match="between 1 and 1000",
    ):
        ExecutionEventProjectionService(
            store=RecordingProjectionStore(
                []
            ),
            default_limit=default_limit,
        )


@pytest.mark.parametrize(
    "limit",
    [0, -1, 1001],
)
def test_service_rejects_invalid_request_limit(
    limit: int,
):
    service = ExecutionEventProjectionService(
        store=RecordingProjectionStore([])
    )

    with pytest.raises(
        ValueError,
        match="between 1 and 1000",
    ):
        service.project_lineage(
            "project-test",
            limit=limit,
        )


def test_service_rejects_empty_project_id():
    service = ExecutionEventProjectionService(
        store=RecordingProjectionStore([])
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.project_lineage("")


def test_service_preserves_projection_errors():
    wrong_project_record = (
        StoredExecutionEvent(
            store_sequence=1,
            event=_event(
                1,
                project_id="project-other",
            ),
        )
    )

    service = ExecutionEventProjectionService(
        store=RecordingProjectionStore(
            [wrong_project_record]
        )
    )

    with pytest.raises(
        Exception,
        match=(
            "does not belong to the "
            "projected project"
        ),
    ):
        service.project_lineage(
            "project-test"
        )
