from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

import pytest

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_projection_service import (
    ExecutionEventProjectionIncompleteSnapshotError,
    ExecutionEventProjectionService,
    ExecutionEventProjectionUnsupportedStoreError,
)
from execution_evidence.execution_event_record_snapshot import (
    ProjectExecutionEventRecordSnapshot,
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
        client_idempotency_key=f"client-{number}",
        ingestion_method="system",
        payload={"number": number},
    )


class SnapshotProjectionStore(
    ExecutionEventStore
):
    def __init__(
        self,
        snapshot: ProjectExecutionEventRecordSnapshot,
    ) -> None:
        self.snapshot = snapshot
        self.calls: List[str] = []

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

    def load_project_event_record_snapshot(
        self,
        project_id: str,
    ) -> ProjectExecutionEventRecordSnapshot:
        self.calls.append(project_id)
        return self.snapshot


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


def _snapshot(
    records: List[StoredExecutionEvent],
    *,
    project_id: str = "project-test",
) -> ProjectExecutionEventRecordSnapshot:
    return ProjectExecutionEventRecordSnapshot(
        project_id=project_id,
        records=tuple(records),
        project_watermark_sequence=(
            max(
                record.store_sequence
                for record in records
            )
            if records
            else 0
        ),
    )


def test_service_loads_complete_snapshot_and_projects():
    first = StoredExecutionEvent(
        store_sequence=4,
        event=_event(1),
    )
    second = StoredExecutionEvent(
        store_sequence=9,
        event=_event(
            2,
            supersedes=1,
        ),
    )

    store = SnapshotProjectionStore(
        _snapshot([first, second])
    )
    service = ExecutionEventProjectionService(
        store=store
    )

    projection = service.project_lineage(
        "project-test"
    )

    assert store.calls == ["project-test"]
    assert (
        projection.projection_through_sequence
        == 9
    )
    assert [
        record.store_sequence
        for record in projection.ordered_records
    ] == [4, 9]
    assert projection.terminal_event_ids == (
        second.event.execution_event_id,
    )


def test_service_projects_more_than_legacy_limit():
    records = [
        StoredExecutionEvent(
            store_sequence=number,
            event=_event(number),
        )
        for number in range(1, 1002)
    ]

    service = ExecutionEventProjectionService(
        store=SnapshotProjectionStore(
            _snapshot(records)
        )
    )

    projection = service.project_lineage(
        "project-test"
    )

    assert len(projection.ordered_records) == 1001
    assert (
        projection.projection_through_sequence
        == 1001
    )


def test_service_rejects_snapshot_for_other_project():
    service = ExecutionEventProjectionService(
        store=SnapshotProjectionStore(
            _snapshot(
                [],
                project_id="project-other",
            )
        )
    )

    with pytest.raises(
        ExecutionEventProjectionIncompleteSnapshotError,
        match="different project",
    ):
        service.project_lineage("project-test")


def test_service_rejects_unsupported_store():
    service = ExecutionEventProjectionService(
        store=UnsupportedProjectionStore()
    )

    with pytest.raises(
        ExecutionEventProjectionUnsupportedStoreError,
        match="complete authoritative project snapshots",
    ):
        service.project_lineage("project-test")


def test_service_rejects_empty_project_id():
    service = ExecutionEventProjectionService(
        store=SnapshotProjectionStore(
            _snapshot([])
        )
    )

    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        service.project_lineage("")


def test_service_uses_event_after_legacy_limit_to_resolve_lineage():
    records = [
        StoredExecutionEvent(
            store_sequence=number,
            event=_event(number),
        )
        for number in range(1, 1001)
    ]

    successor = StoredExecutionEvent(
        store_sequence=1001,
        event=_event(
            1001,
            supersedes=1,
        ),
    )

    service = ExecutionEventProjectionService(
        store=SnapshotProjectionStore(
            _snapshot(
                records + [successor]
            )
        )
    )

    projection = service.project_lineage(
        "project-test"
    )

    original_event_id = _event_id(1)
    successor_event_id = _event_id(1001)

    assert len(projection.ordered_records) == 1001
    assert (
        projection.projection_through_sequence
        == 1001
    )
    assert (
        original_event_id
        not in projection.terminal_event_ids
    )
    assert (
        successor_event_id
        in projection.terminal_event_ids
    )
    assert (
        successor_event_id
        in projection.authoritative_event_ids
    )


def test_snapshot_model_rejects_out_of_order_records():
    first = StoredExecutionEvent(
        store_sequence=4,
        event=_event(1),
    )
    second = StoredExecutionEvent(
        store_sequence=9,
        event=_event(2),
    )

    with pytest.raises(
        ValueError,
        match="ascending storage sequence",
    ):
        ProjectExecutionEventRecordSnapshot(
            project_id="project-test",
            records=(second, first),
            project_watermark_sequence=9,
        )


def test_service_rejects_snapshot_below_authoritative_watermark():
    record = StoredExecutionEvent(
        store_sequence=4,
        event=_event(1),
    )

    snapshot = ProjectExecutionEventRecordSnapshot(
        project_id="project-test",
        records=(record,),
        project_watermark_sequence=9,
    )

    service = ExecutionEventProjectionService(
        store=SnapshotProjectionStore(snapshot)
    )

    with pytest.raises(
        ExecutionEventProjectionIncompleteSnapshotError,
        match="authoritative project watermark",
    ):
        service.project_lineage("project-test")
