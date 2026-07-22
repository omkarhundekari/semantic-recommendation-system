from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from execution_evidence.execution_event_store import (
    StoredExecutionEvent,
)
from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, rows):
        self._rows = rows
        self.sql = None
        self.parameters = None
        self.closed = False

    def execute(self, sql, parameters):
        self.sql = sql
        self.parameters = parameters
        return _FakeCursor(self._rows)

    def close(self):
        self.closed = True


def _build_store(rows):
    store = SQLiteExecutionEventStore.__new__(
        SQLiteExecutionEventStore
    )
    connection = _FakeConnection(rows)

    store._workspace_id = "workspace-test"
    store._connect = lambda: connection
    store._event_from_row = lambda row: row["event"]

    return store, connection


def test_stored_execution_event_is_immutable():
    record = StoredExecutionEvent(
        store_sequence=1,
        event=object(),
    )

    with pytest.raises(FrozenInstanceError):
        record.store_sequence = 2


def test_list_project_event_records_returns_storage_order():
    first_event = object()
    second_event = object()

    store, connection = _build_store(
        [
            {
                "execution_event_row_id": 4,
                "event": first_event,
            },
            {
                "execution_event_row_id": 9,
                "event": second_event,
            },
        ]
    )

    records = store.list_project_event_records(
        "project-test",
        limit=25,
    )

    assert [
        record.store_sequence
        for record in records
    ] == [4, 9]

    assert [
        record.event
        for record in records
    ] == [
        first_event,
        second_event,
    ]

    assert (
        "ORDER BY"
        in connection.sql
    )
    assert (
        "execution_event_row_id ASC"
        in connection.sql
    )
    assert connection.parameters == (
        "workspace-test",
        "project-test",
        25,
    )
    assert connection.closed is True


def test_list_project_event_records_is_workspace_scoped():
    store, connection = _build_store([])

    assert (
        store.list_project_event_records(
            "project-other"
        )
        == []
    )

    normalized_sql = " ".join(
        connection.sql.split()
    )

    assert "workspace_id = ?" in normalized_sql
    assert "project_id = ?" in normalized_sql
    assert connection.parameters == (
        "workspace-test",
        "project-other",
        100,
    )


@pytest.mark.parametrize(
    "limit",
    [0, -1, 1001],
)
def test_list_project_event_records_rejects_invalid_limit(
    limit,
):
    store, _ = _build_store([])

    with pytest.raises(
        ValueError,
        match=(
            "between 1 and 1000"
        ),
    ):
        store.list_project_event_records(
            "project-test",
            limit=limit,
        )


@pytest.mark.parametrize(
    "limit",
    [1, 100, 1000],
)
def test_list_project_event_records_accepts_valid_limit(
    limit,
):
    store, connection = _build_store([])

    assert (
        store.list_project_event_records(
            "project-test",
            limit=limit,
        )
        == []
    )

    assert connection.parameters[-1] == limit


def test_existing_project_event_list_keeps_timeline_order():
    newest_event = object()
    oldest_event = object()

    store, connection = _build_store(
        [
            {
                "execution_event_row_id": 9,
                "event": newest_event,
            },
            {
                "execution_event_row_id": 4,
                "event": oldest_event,
            },
        ]
    )

    events = store.list_project_events(
        "project-test"
    )

    assert events == [
        newest_event,
        oldest_event,
    ]

    normalized_sql = " ".join(
        connection.sql.split()
    )

    assert (
        "occurred_at DESC, "
        "recorded_at DESC, "
        "execution_event_id DESC"
        in normalized_sql
    )


def test_storage_order_does_not_use_event_timestamps():
    store, connection = _build_store([])

    store.list_project_event_records(
        "project-test"
    )

    normalized_sql = " ".join(
        connection.sql.split()
    )

    assert "execution_event_row_id ASC" in normalized_sql
    assert "occurred_at" not in normalized_sql
    assert "recorded_at" not in normalized_sql
