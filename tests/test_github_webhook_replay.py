from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
)
from execution_evidence.github_webhook_adapter import (
    adapt_github_push,
)
from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


UTC = timezone.utc
RECORDED_AT = datetime(
    2026,
    7,
    21,
    12,
    1,
    tzinfo=UTC,
)


def _insert_project(
    database_path: Path,
) -> None:
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(workspace_id)
            DO NOTHING
            """,
            (
                "local",
                "2026-07-21T12:00:00+00:00",
                "2026-07-21T12:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "proj_test",
                "local",
                "Replay test project",
                "active",
                "2026-07-21T12:00:00+00:00",
                "2026-07-21T12:00:00+00:00",
            ),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()


def _push_payload(
    *,
    after_sha: str = "b" * 40,
) -> dict:
    return {
        "ref": "refs/heads/main",
        "before": "a" * 40,
        "after": after_sha,
        "created": False,
        "deleted": False,
        "forced": False,
        "compare": (
            "https://github.com/owner/repo/"
            "compare/aaaaaaaa...bbbbbbbb"
        ),
        "repository": {
            "id": 123,
            "full_name": "owner/repo",
            "pushed_at": 1784635200,
        },
        "sender": {
            "id": 456,
            "login": "octocat",
        },
        "commits": [
            {"id": after_sha},
        ],
    }


def _adapt_push(
    *,
    delivery_id: str,
    after_sha: str = "b" * 40,
):
    return adapt_github_push(
        project_id="proj_test",
        delivery_id=delivery_id,
        recorded_at=RECORDED_AT,
        payload=_push_payload(
            after_sha=after_sha,
        ),
    )


def _count_events(
    database_path: Path,
) -> int:
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS event_count
            FROM project_execution_events
            WHERE
                workspace_id = ?
                AND project_id = ?
            """,
            (
                "local",
                "proj_test",
            ),
        ).fetchone()

        return int(row["event_count"])
    finally:
        connection.close()


def test_identical_github_delivery_retry_returns_existing_event(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)
    store = SQLiteExecutionEventStore(database_path)

    first_event = _adapt_push(
        delivery_id="delivery-123",
    )
    retry_event = _adapt_push(
        delivery_id="delivery-123",
    )

    first_result = store.append(first_event)
    retry_result = store.append(retry_event)

    assert first_result.created is True
    assert retry_result.created is False
    assert (
        retry_result.event.execution_event_id
        == first_result.event.execution_event_id
    )
    assert _count_events(database_path) == 1


def test_github_delivery_reuse_with_changed_payload_conflicts(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)
    store = SQLiteExecutionEventStore(database_path)

    store.append(
        _adapt_push(
            delivery_id="delivery-123",
        )
    )

    with pytest.raises(
        ExecutionEventIdempotencyConflictError
    ):
        store.append(
            _adapt_push(
                delivery_id="delivery-123",
                after_sha="c" * 40,
            )
        )

    assert _count_events(database_path) == 1


def test_different_github_delivery_ids_create_distinct_events(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)
    store = SQLiteExecutionEventStore(database_path)

    first_result = store.append(
        _adapt_push(
            delivery_id="delivery-123",
        )
    )
    second_result = store.append(
        _adapt_push(
            delivery_id="delivery-456",
        )
    )

    assert first_result.created is True
    assert second_result.created is True
    assert (
        first_result.event.execution_event_id
        != second_result.event.execution_event_id
    )
    assert _count_events(database_path) == 2
