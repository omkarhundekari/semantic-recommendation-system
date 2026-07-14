from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from planning.roadmap_snapshot import RoadmapSnapshot


class RoadmapRegistryError(RuntimeError):
    pass


class RoadmapSnapshotConflictError(
    RoadmapRegistryError
):
    pass


class StoredRoadmapSnapshot(BaseModel):
    project_direction_id: str = Field(
        min_length=1,
    )
    response_direction_id: str = Field(
        min_length=1,
    )
    title: str = Field(
        min_length=1,
    )
    snapshot: RoadmapSnapshot
    created_at: datetime
    supersedes_id: Optional[str] = None


def create_stored_roadmap_snapshot(
    *,
    response_direction_id: str,
    title: str,
    snapshot: RoadmapSnapshot,
    created_at: datetime,
    supersedes_id: Optional[str] = None,
) -> StoredRoadmapSnapshot:
    return StoredRoadmapSnapshot(
        project_direction_id=str(uuid4()),
        response_direction_id=(
            response_direction_id.strip()
        ),
        title=title.strip(),
        snapshot=snapshot,
        created_at=created_at,
        supersedes_id=(
            supersedes_id.strip()
            if supersedes_id
            else None
        ),
    )


class RoadmapSnapshotRegistry(ABC):
    @abstractmethod
    def create(
        self,
        record: StoredRoadmapSnapshot,
    ) -> StoredRoadmapSnapshot:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        project_direction_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def list_snapshots(
        self,
    ) -> List[StoredRoadmapSnapshot]:
        raise NotImplementedError


class SQLiteRoadmapSnapshotRegistry(
    RoadmapSnapshotRegistry
):
    def __init__(
        self,
        path: Path | str,
        *,
        workspace_id: str = "local",
        initialize_schema: bool = True,
    ) -> None:
        self._path = Path(path)
        self._workspace_id = (
            workspace_id.strip()
        )

        if not self._workspace_id:
            raise ValueError(
                "Roadmap registry workspace ID "
                "must not be empty."
            )

        if initialize_schema:
            initialize_execution_evidence_database(
                self._path
            )

        self._ensure_workspace()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def create(
        self,
        record: StoredRoadmapSnapshot,
    ) -> StoredRoadmapSnapshot:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_workspace_on_connection(
                connection
            )

            existing = self._load_on_connection(
                connection,
                record.project_direction_id,
            )

            if existing is not None:
                if existing == record:
                    connection.execute("COMMIT")
                    return existing.model_copy(
                        deep=True
                    )

                raise RoadmapSnapshotConflictError(
                    "Project direction ID already "
                    "references a different immutable "
                    "roadmap snapshot."
                )

            connection.execute(
                """
                INSERT INTO roadmap_registry (
                    workspace_id,
                    project_direction_id,
                    response_direction_id,
                    title,
                    roadmap_hash,
                    snapshot_json,
                    created_at,
                    supersedes_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._workspace_id,
                    record.project_direction_id,
                    record.response_direction_id,
                    record.title,
                    record.snapshot.roadmap_hash,
                    record.snapshot.model_dump_json(),
                    record.created_at.isoformat(),
                    record.supersedes_id,
                ),
            )

            connection.execute("COMMIT")

            return record.model_copy(deep=True)
        except RoadmapSnapshotConflictError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise RoadmapSnapshotConflictError(
                "Roadmap snapshot registry "
                "constraint conflict."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise RoadmapRegistryError(
                "Could not create roadmap snapshot "
                "registry record."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        project_direction_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        connection = self._connect()

        try:
            record = self._load_on_connection(
                connection,
                project_direction_id.strip(),
            )

            return (
                record.model_copy(deep=True)
                if record is not None
                else None
            )
        except (
            sqlite3.Error,
            ValueError,
        ) as error:
            raise RoadmapRegistryError(
                "Could not load roadmap snapshot "
                "registry record."
            ) from error
        finally:
            connection.close()

    def list_snapshots(
        self,
    ) -> List[StoredRoadmapSnapshot]:
        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT
                    project_direction_id,
                    response_direction_id,
                    title,
                    snapshot_json,
                    created_at,
                    supersedes_id
                FROM roadmap_registry
                WHERE workspace_id = ?
                ORDER BY
                    created_at DESC,
                    project_direction_id
                """,
                (self._workspace_id,),
            ).fetchall()

            return [
                self._record_from_row(row)
                for row in rows
            ]
        except (
            sqlite3.Error,
            ValueError,
        ) as error:
            raise RoadmapRegistryError(
                "Could not list roadmap snapshot "
                "registry records."
            ) from error
        finally:
            connection.close()

    def _load_on_connection(
        self,
        connection: sqlite3.Connection,
        project_direction_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        row = connection.execute(
            """
            SELECT
                project_direction_id,
                response_direction_id,
                title,
                snapshot_json,
                created_at,
                supersedes_id
            FROM roadmap_registry
            WHERE
                workspace_id = ?
                AND project_direction_id = ?
            """,
            (
                self._workspace_id,
                project_direction_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return self._record_from_row(row)

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> StoredRoadmapSnapshot:
        return StoredRoadmapSnapshot(
            project_direction_id=(
                row["project_direction_id"]
            ),
            response_direction_id=(
                row["response_direction_id"]
            ),
            title=row["title"],
            snapshot=(
                RoadmapSnapshot.model_validate_json(
                    row["snapshot_json"]
                )
            ),
            created_at=row["created_at"],
            supersedes_id=row["supersedes_id"],
        )

    def _connect(self) -> sqlite3.Connection:
        try:
            return (
                connect_execution_evidence_database(
                    self._path
                )
            )
        except Exception as error:
            raise RoadmapRegistryError(
                "Could not connect to roadmap "
                "snapshot registry storage."
            ) from error

    def _ensure_workspace(self) -> None:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_workspace_on_connection(
                connection
            )
            connection.execute("COMMIT")
        except sqlite3.Error as error:
            self._rollback(connection)
            raise RoadmapRegistryError(
                "Could not initialize roadmap "
                "registry workspace."
            ) from error
        finally:
            connection.close()

    def _ensure_workspace_on_connection(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                ),
                strftime(
                    '%Y-%m-%dT%H:%M:%fZ',
                    'now'
                )
            )
            ON CONFLICT(workspace_id)
            DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (self._workspace_id,),
        )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
