from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import List, Optional

from execution_evidence.execution_event import (
    ExecutionEvent,
    ExecutionEventAppendResult,
)
from execution_evidence.execution_event_payload import (
    EXECUTION_EVENT_PAYLOAD_REGISTRY,
    ExecutionEventPayload,
)
from execution_evidence.execution_event_store import (
    ExecutionEventIdempotencyConflictError,
    ExecutionEventProjectNotFoundError,
    ExecutionEventStore,
    ExecutionEventStoreError,
    ExecutionEventSupersessionScopeError,
    ExecutionEventSupersessionTargetNotFoundError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


DEFAULT_WORKSPACE_ID = "local"



def _serialize_execution_event_payload(
    payload: object,
) -> object:
    if isinstance(
        payload,
        ExecutionEventPayload,
    ):
        return payload.model_dump(mode="json")

    return payload


def _deserialize_execution_event_payload(
    *,
    event_type: str,
    payload_json: str,
) -> object:
    payload = json.loads(payload_json)
    payload_type = (
        EXECUTION_EVENT_PAYLOAD_REGISTRY.get(
            event_type
        )
    )

    if payload_type is None:
        return payload

    if not isinstance(payload, dict):
        raise ExecutionEventStoreError(
            "Stored typed execution event payload "
            "must be a JSON object."
        )

    try:
        return payload_type.model_validate(payload)
    except Exception as error:
        raise ExecutionEventStoreError(
            "Stored execution event payload does not "
            f"match event type '{event_type}'."
        ) from error


class SQLiteExecutionEventStore(
    ExecutionEventStore
):
    def __init__(
        self,
        path: Path | str,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        initialize_schema: bool = True,
    ) -> None:
        if not workspace_id.strip():
            raise ValueError(
                "SQLite workspace ID must be non-empty."
            )

        self._path = Path(path)
        self._workspace_id = workspace_id.strip()

        if initialize_schema:
            initialize_execution_evidence_database(
                self._path
            )

    @property
    def path(self) -> Path:
        return self._path

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def append(
        self,
        event: ExecutionEvent,
    ) -> ExecutionEventAppendResult:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            project = connection.execute(
                """
                SELECT project_row_id
                FROM projects
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                """,
                (
                    self._workspace_id,
                    event.project_id,
                ),
            ).fetchone()

            if project is None:
                raise (
                    ExecutionEventProjectNotFoundError(
                        "Execution event project does "
                        "not exist."
                    )
                )

            existing = self._find_idempotent_event(
                connection,
                event,
            )

            fingerprint = (
                event.immutable_fingerprint()
            )

            if existing is not None:
                if (
                    str(existing["event_fingerprint"])
                    != fingerprint
                ):
                    raise (
                        ExecutionEventIdempotencyConflictError(
                            "Execution event idempotency "
                            "key was reused with different "
                            "immutable content."
                        )
                    )

                authoritative = (
                    self._event_from_row(existing)
                )
                connection.execute("COMMIT")

                return ExecutionEventAppendResult(
                    event=authoritative,
                    created=False,
                )

            self._validate_supersession_target(
                connection,
                event=event,
                project_row_id=int(
                    project["project_row_id"]
                ),
            )

            connection.execute(
                """
                INSERT INTO project_execution_events (
                    execution_event_id,
                    supersedes_execution_event_id,
                    workspace_id,
                    project_row_id,
                    project_id,
                    event_type,
                    occurred_at,
                    recorded_at,
                    actor_id,
                    ingested_by_id,
                    source_provider,
                    source_account_id,
                    external_resource_id,
                    external_entity_type,
                    external_entity_id,
                    provider_idempotency_key,
                    client_idempotency_key,
                    ingestion_method,
                    source_payload_hash,
                    verified_at,
                    visibility,
                    payload_json,
                    event_fingerprint,
                    created_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?
                )
                """,
                (
                    event.execution_event_id,
                    event.supersedes_execution_event_id,
                    self._workspace_id,
                    int(project["project_row_id"]),
                    event.project_id,
                    event.event_type,
                    event.occurred_at.isoformat(),
                    event.recorded_at.isoformat(),
                    event.actor_id,
                    event.ingested_by_id,
                    event.source_provider,
                    event.source_account_id,
                    event.external_resource_id,
                    event.external_entity_type,
                    event.external_entity_id,
                    event.provider_idempotency_key,
                    event.client_idempotency_key,
                    event.ingestion_method,
                    event.source_payload_hash,
                    (
                        event.verified_at.isoformat()
                        if event.verified_at is not None
                        else None
                    ),
                    event.visibility,
                    json.dumps(
                        _serialize_execution_event_payload(
                            event.payload
                        ),
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ),
                    fingerprint,
                    event.recorded_at.isoformat(),
                ),
            )

            stored = self._load_on_connection(
                connection,
                event.execution_event_id,
            )

            if stored is None:
                raise ExecutionEventStoreError(
                    "Stored execution event could not "
                    "be reloaded."
                )

            connection.execute("COMMIT")

            return ExecutionEventAppendResult(
                event=stored,
                created=True,
            )
        except (
            ExecutionEventProjectNotFoundError,
            ExecutionEventIdempotencyConflictError,
            ExecutionEventSupersessionScopeError,
            ExecutionEventSupersessionTargetNotFoundError,
            ExecutionEventStoreError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)

            replay = self._load_replay_after_conflict(
                event
            )

            if replay is not None:
                return replay

            raise ExecutionEventStoreError(
                "Execution event violated a storage "
                "integrity constraint."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise ExecutionEventStoreError(
                "Could not append execution event."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        connection = self._connect()

        try:
            return self._load_on_connection(
                connection,
                execution_event_id,
            )
        except sqlite3.Error as error:
            raise ExecutionEventStoreError(
                "Could not load execution event."
            ) from error
        finally:
            connection.close()

    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        if limit < 1 or limit > 1000:
            raise ValueError(
                "Execution event list limit must be "
                "between 1 and 1000."
            )

        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT *
                FROM project_execution_events
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                ORDER BY
                    occurred_at DESC,
                    recorded_at DESC,
                    execution_event_id DESC
                LIMIT ?
                """,
                (
                    self._workspace_id,
                    project_id,
                    limit,
                ),
            ).fetchall()

            return [
                self._event_from_row(row)
                for row in rows
            ]
        except sqlite3.Error as error:
            raise ExecutionEventStoreError(
                "Could not list project execution "
                "events."
            ) from error
        finally:
            connection.close()

    def _validate_supersession_target(
        self,
        connection: sqlite3.Connection,
        *,
        event: ExecutionEvent,
        project_row_id: int,
    ) -> None:
        target_id = (
            event.supersedes_execution_event_id
        )

        if target_id is None:
            return

        target = connection.execute(
            """
            SELECT
                project_row_id,
                project_id
            FROM project_execution_events
            WHERE
                workspace_id = ?
                AND execution_event_id = ?
            """,
            (
                self._workspace_id,
                target_id,
            ),
        ).fetchone()

        if target is None:
            raise (
                ExecutionEventSupersessionTargetNotFoundError(
                    "Superseded execution event does "
                    "not exist."
                )
            )

        if (
            int(target["project_row_id"])
            != project_row_id
            or str(target["project_id"])
            != event.project_id
        ):
            raise ExecutionEventSupersessionScopeError(
                "Superseded execution event belongs "
                "to a different project."
            )

    def _find_idempotent_event(
        self,
        connection: sqlite3.Connection,
        event: ExecutionEvent,
    ) -> Optional[sqlite3.Row]:
        matches = []

        if event.provider_idempotency_key is not None:
            row = connection.execute(
                """
                SELECT *
                FROM project_execution_events
                WHERE
                    workspace_id = ?
                    AND provider_idempotency_key = ?
                """,
                (
                    self._workspace_id,
                    event.provider_idempotency_key,
                ),
            ).fetchone()

            if row is not None:
                matches.append(row)

        if event.client_idempotency_key is not None:
            row = connection.execute(
                """
                SELECT *
                FROM project_execution_events
                WHERE
                    workspace_id = ?
                    AND client_idempotency_key = ?
                """,
                (
                    self._workspace_id,
                    event.client_idempotency_key,
                ),
            ).fetchone()

            if row is not None:
                matches.append(row)

        if not matches:
            return None

        event_ids = {
            str(row["execution_event_id"])
            for row in matches
        }

        if len(event_ids) != 1:
            raise ExecutionEventIdempotencyConflictError(
                "Execution event idempotency keys "
                "resolve to different stored events."
            )

        return matches[0]

    def _load_on_connection(
        self,
        connection: sqlite3.Connection,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        row = connection.execute(
            """
            SELECT *
            FROM project_execution_events
            WHERE
                workspace_id = ?
                AND execution_event_id = ?
            """,
            (
                self._workspace_id,
                execution_event_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return self._event_from_row(row)

    def _load_replay_after_conflict(
        self,
        event: ExecutionEvent,
    ) -> Optional[ExecutionEventAppendResult]:
        connection = self._connect()

        try:
            existing = self._find_idempotent_event(
                connection,
                event,
            )

            if existing is None:
                return None

            if (
                str(existing["event_fingerprint"])
                != event.immutable_fingerprint()
            ):
                raise (
                    ExecutionEventIdempotencyConflictError(
                        "Execution event idempotency "
                        "key was reused with different "
                        "immutable content."
                    )
                )

            return ExecutionEventAppendResult(
                event=self._event_from_row(existing),
                created=False,
            )
        finally:
            connection.close()

    @staticmethod
    def _event_from_row(
        row: sqlite3.Row,
    ) -> ExecutionEvent:
        return ExecutionEvent(
            execution_event_id=row[
                "execution_event_id"
            ],
            supersedes_execution_event_id=row[
                "supersedes_execution_event_id"
            ],
            project_id=row["project_id"],
            event_type=row["event_type"],
            occurred_at=row["occurred_at"],
            recorded_at=row["recorded_at"],
            actor_id=row["actor_id"],
            ingested_by_id=row["ingested_by_id"],
            source_provider=row["source_provider"],
            source_account_id=row[
                "source_account_id"
            ],
            external_resource_id=row[
                "external_resource_id"
            ],
            external_entity_type=row[
                "external_entity_type"
            ],
            external_entity_id=row[
                "external_entity_id"
            ],
            provider_idempotency_key=row[
                "provider_idempotency_key"
            ],
            client_idempotency_key=row[
                "client_idempotency_key"
            ],
            ingestion_method=row[
                "ingestion_method"
            ],
            source_payload_hash=row[
                "source_payload_hash"
            ],
            verified_at=row["verified_at"],
            visibility=row["visibility"],
            payload=_deserialize_execution_event_payload(
                event_type=row["event_type"],
                payload_json=row["payload_json"],
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        try:
            return connect_execution_evidence_database(
                self._path
            )
        except Exception as error:
            raise ExecutionEventStoreError(
                "Could not connect to execution event "
                "storage."
            ) from error

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
