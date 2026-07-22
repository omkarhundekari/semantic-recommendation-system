from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from typing import Optional

import pytest
from pydantic import ValidationError

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_payload import (
    GitHubRefUpdatedPayload,
)
from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
    ExecutionEventProjectNotFoundError,
)
from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


UTC = timezone.utc


def _insert_project(
    database_path: Path,
    *,
    workspace_id: str = "local",
    project_id: str = "proj_test",
    status: str = "active",
) -> None:
    initialize_execution_evidence_database(
        database_path
    )
    connection = (
        connect_execution_evidence_database(
            database_path
        )
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
                workspace_id,
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
                project_id,
                workspace_id,
                "Test project",
                status,
                "2026-07-21T12:00:00+00:00",
                "2026-07-21T12:00:00+00:00",
            ),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()


def _event(
    *,
    execution_event_id: str = "evt_one",
    project_id: str = "proj_test",
    event_type: str = "commit.created",
    occurred_at: Optional[datetime] = None,
    recorded_at: Optional[datetime] = None,
    provider_idempotency_key: Optional[
        str
    ] = "github:account:repo:commit:abc",
    client_idempotency_key: Optional[
        str
    ] = None,
    ingestion_method: str = "webhook",
    payload: Optional[object] = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        execution_event_id=execution_event_id,
        project_id=project_id,
        event_type=event_type,
        occurred_at=occurred_at
        or datetime(
            2026,
            7,
            21,
            12,
            0,
            tzinfo=UTC,
        ),
        recorded_at=recorded_at
        or datetime(
            2026,
            7,
            21,
            12,
            1,
            tzinfo=UTC,
        ),
        actor_id="user_omkar",
        ingested_by_id="system_github",
        source_provider="github",
        source_account_id="github-account",
        external_resource_id="repository-123",
        external_entity_type="commit",
        external_entity_id="abc",
        provider_idempotency_key=(
            provider_idempotency_key
        ),
        client_idempotency_key=(
            client_idempotency_key
        ),
        ingestion_method=ingestion_method,
        source_payload_hash="sha256:payload",
        verified_at=datetime(
            2026,
            7,
            21,
            12,
            1,
            tzinfo=UTC,
        ),
        visibility="project",
        payload=payload
        or {
            "repository": "owner/repository",
            "commit_sha": "abc",
        },
    )


def test_append_and_load_event(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    event = _event()

    result = store.append(event)
    loaded = store.load(
        event.execution_event_id
    )

    assert result.created is True
    assert result.event == event
    assert loaded == event


def test_identical_provider_replay_returns_authoritative_event(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    first = store.append(_event())

    replay = store.append(
        _event(
            execution_event_id="evt_retry",
            recorded_at=datetime(
                2026,
                7,
                21,
                12,
                5,
                tzinfo=UTC,
            ),
        )
    )

    assert first.created is True
    assert replay.created is False
    assert (
        replay.event.execution_event_id
        == "evt_one"
    )
    assert (
        replay.event.recorded_at
        == first.event.recorded_at
    )


def test_provider_replay_with_different_content_conflicts(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    store.append(_event())

    with pytest.raises(
        ExecutionEventIdempotencyConflictError
    ):
        store.append(
            _event(
                execution_event_id="evt_conflict",
                payload={
                    "repository": "owner/repository",
                    "commit_sha": "different",
                },
            )
        )


def test_client_idempotency_key_replays_event(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )

    first_event = _event(
        provider_idempotency_key=None,
        client_idempotency_key="request-123",
        ingestion_method="api",
    )

    first = store.append(first_event)
    replay = store.append(
        first_event.model_copy(
            update={
                "execution_event_id": "evt_retry",
                "recorded_at": datetime(
                    2026,
                    7,
                    21,
                    12,
                    10,
                    tzinfo=UTC,
                ),
            }
        )
    )

    assert first.created is True
    assert replay.created is False
    assert (
        replay.event.execution_event_id
        == first.event.execution_event_id
    )


def test_append_requires_existing_project(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLiteExecutionEventStore(
        database_path
    )

    with pytest.raises(
        ExecutionEventProjectNotFoundError
    ):
        store.append(_event())


@pytest.mark.parametrize(
    "status",
    [
        "archived",
        "deleted",
    ],
)
def test_events_remain_readable_for_inactive_projects(
    tmp_path: Path,
    status: str,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    stored = store.append(_event()).event

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            UPDATE projects
            SET status = ?
            WHERE
                workspace_id = 'local'
                AND project_id = 'proj_test'
            """,
            (status,),
        )
    finally:
        connection.close()

    assert store.load(
        stored.execution_event_id
    ) == stored
    assert store.list_project_events(
        "proj_test"
    ) == [stored]


def test_list_project_events_has_deterministic_order(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )

    events = [
        _event(
            execution_event_id="evt_a",
            provider_idempotency_key="key-a",
            occurred_at=datetime(
                2026,
                7,
                21,
                12,
                0,
                tzinfo=UTC,
            ),
            recorded_at=datetime(
                2026,
                7,
                21,
                12,
                1,
                tzinfo=UTC,
            ),
        ),
        _event(
            execution_event_id="evt_c",
            provider_idempotency_key="key-c",
            occurred_at=datetime(
                2026,
                7,
                21,
                13,
                0,
                tzinfo=UTC,
            ),
            recorded_at=datetime(
                2026,
                7,
                21,
                13,
                1,
                tzinfo=UTC,
            ),
        ),
        _event(
            execution_event_id="evt_b",
            provider_idempotency_key="key-b",
            occurred_at=datetime(
                2026,
                7,
                21,
                12,
                0,
                tzinfo=UTC,
            ),
            recorded_at=datetime(
                2026,
                7,
                21,
                12,
                2,
                tzinfo=UTC,
            ),
        ),
    ]

    for event in events:
        store.append(event)

    listed = store.list_project_events(
        "proj_test"
    )

    assert [
        event.execution_event_id
        for event in listed
    ] == [
        "evt_c",
        "evt_b",
        "evt_a",
    ]


def test_event_rows_cannot_be_updated_or_deleted(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    store.append(_event())

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                UPDATE project_execution_events
                SET event_type = 'changed'
                WHERE execution_event_id = 'evt_one'
                """
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                DELETE FROM project_execution_events
                WHERE execution_event_id = 'evt_one'
                """
            )
    finally:
        connection.close()


def test_workspace_isolation_applies_to_public_event_ids(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    _insert_project(
        database_path,
        workspace_id="workspace-one",
        project_id="proj_shared",
    )
    _insert_project(
        database_path,
        workspace_id="workspace-two",
        project_id="proj_shared",
    )

    first_store = SQLiteExecutionEventStore(
        database_path,
        workspace_id="workspace-one",
    )
    second_store = SQLiteExecutionEventStore(
        database_path,
        workspace_id="workspace-two",
    )

    first = _event(
        execution_event_id="evt_shared",
        project_id="proj_shared",
        provider_idempotency_key="shared-key",
    )
    second = first.model_copy(
        update={
            "payload": {
                "workspace": "workspace-two",
            },
        }
    )

    assert first_store.append(first).created
    assert second_store.append(second).created

    assert first_store.load(
        "evt_shared"
    ).payload != second_store.load(
        "evt_shared"
    ).payload


def test_concurrent_duplicate_delivery_creates_one_event(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    barrier = Barrier(2)

    def append_from_worker(
        execution_event_id: str,
    ):
        store = SQLiteExecutionEventStore(
            database_path,
            initialize_schema=False,
        )
        barrier.wait()

        return store.append(
            _event(
                execution_event_id=(
                    execution_event_id
                ),
            )
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                append_from_worker,
                "evt_worker_one",
            ),
            executor.submit(
                append_from_worker,
                "evt_worker_two",
            ),
        ]
        results = [
            future.result()
            for future in futures
        ]

    assert sorted(
        result.created
        for result in results
    ) == [
        False,
        True,
    ]

    stored_ids = {
        result.event.execution_event_id
        for result in results
    }
    assert len(stored_ids) == 1

    store = SQLiteExecutionEventStore(
        database_path,
        initialize_schema=False,
    )
    assert len(
        store.list_project_events(
            "proj_test"
        )
    ) == 1


def test_independent_concurrent_appends_both_succeed(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    barrier = Barrier(2)

    def append_from_worker(
        event_id: str,
        provider_key: str,
    ):
        store = SQLiteExecutionEventStore(
            database_path,
            initialize_schema=False,
        )
        barrier.wait()

        return store.append(
            _event(
                execution_event_id=event_id,
                provider_idempotency_key=(
                    provider_key
                ),
            )
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        futures = [
            executor.submit(
                append_from_worker,
                "evt_worker_one",
                "provider-one",
            ),
            executor.submit(
                append_from_worker,
                "evt_worker_two",
                "provider-two",
            ),
        ]
        results = [
            future.result()
            for future in futures
        ]

    assert all(
        result.created
        for result in results
    )

    store = SQLiteExecutionEventStore(
        database_path,
        initialize_schema=False,
    )
    assert len(
        store.list_project_events(
            "proj_test"
        )
    ) == 2


def test_naive_event_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        _event(
            occurred_at=datetime(
                2026,
                7,
                21,
                12,
                0,
            )
        )


def test_webhook_requires_provider_idempotency_key():
    with pytest.raises(ValidationError):
        _event(
            provider_idempotency_key=None,
            client_idempotency_key="request-only",
        )



def test_typed_payload_survives_sqlite_round_trip(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    _insert_project(database_path)

    store = SQLiteExecutionEventStore(
        database_path
    )
    payload = GitHubRefUpdatedPayload(
        repository_id="123",
        ref="refs/heads/main",
        before_sha="a" * 40,
        after_sha="b" * 40,
        created=False,
        deleted=False,
        forced=False,
        included_commit_count=2,
        sender_id="456",
    )
    event = _event(
        execution_event_id="evt_github_ref",
        event_type="github.ref.updated",
        provider_idempotency_key=(
            "github:delivery:ref-update-123"
        ),
        payload=payload,
    )

    result = store.append(event)
    loaded = store.load(
        event.execution_event_id
    )

    assert result.created is True
    assert result.event == event
    assert loaded == event
    assert isinstance(
        result.event.payload,
        GitHubRefUpdatedPayload,
    )
    assert isinstance(
        loaded.payload,
        GitHubRefUpdatedPayload,
    )
    assert loaded.payload.ref == "refs/heads/main"
    assert loaded.payload.after_sha == "b" * 40
