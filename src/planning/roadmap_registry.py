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
    project_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
    roadmap_snapshot_id: Optional[str] = Field(
        default=None,
        min_length=1,
    )
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
    project_id: Optional[str] = None,
    supersedes_id: Optional[str] = None,
) -> StoredRoadmapSnapshot:
    return StoredRoadmapSnapshot(
        project_id=(
            project_id.strip()
            if project_id is not None
            else f"proj_{uuid4()}"
        ),
        roadmap_snapshot_id=f"snap_{uuid4()}",
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
    def create_many(
        self,
        records: List[StoredRoadmapSnapshot],
    ) -> List[StoredRoadmapSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        project_direction_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def load_by_snapshot_id(
        self,
        roadmap_snapshot_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        raise NotImplementedError

    @abstractmethod
    def load_by_durable_identity(
        self,
        *,
        project_id: str,
        roadmap_snapshot_id: str,
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
        return self.create_many([record])[0]

    def create_many(
        self,
        records: List[StoredRoadmapSnapshot],
    ) -> List[StoredRoadmapSnapshot]:
        if not records:
            return []

        project_direction_ids = [
            record.project_direction_id
            for record in records
        ]

        if len(project_direction_ids) != len(
            set(project_direction_ids)
        ):
            raise RoadmapSnapshotConflictError(
                "A roadmap snapshot batch contains "
                "duplicate project direction IDs."
            )

        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")
            self._ensure_workspace_on_connection(
                connection
            )

            stored_records = []

            for record in records:
                identified = self._identify_record(
                    record
                )
                existing = self._load_on_connection(
                    connection,
                    identified.project_direction_id,
                )

                if existing is not None:
                    if existing == identified:
                        stored_records.append(
                            existing.model_copy(
                                deep=True
                            )
                        )
                        continue

                    raise RoadmapSnapshotConflictError(
                        "Project direction ID already "
                        "references a different immutable "
                        "roadmap snapshot."
                    )

                project_row_id = (
                    self._ensure_project_on_connection(
                        connection,
                        identified,
                    )
                )

                if identified.supersedes_id is not None:
                    predecessor = connection.execute(
                        """
                        SELECT project_row_id
                        FROM roadmap_registry
                        WHERE
                            workspace_id = ?
                            AND project_direction_id = ?
                        """,
                        (
                            self._workspace_id,
                            identified.supersedes_id,
                        ),
                    ).fetchone()

                    if predecessor is None:
                        raise RoadmapSnapshotConflictError(
                            "Superseded roadmap snapshot "
                            "does not exist in this workspace."
                        )

                    if (
                        int(predecessor["project_row_id"])
                        != project_row_id
                    ):
                        raise RoadmapSnapshotConflictError(
                            "A roadmap snapshot may supersede "
                            "only a snapshot from the same "
                            "durable project."
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
                        supersedes_id,
                        project_row_id,
                        roadmap_snapshot_id
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        self._workspace_id,
                        identified.project_direction_id,
                        identified.response_direction_id,
                        identified.title,
                        identified.snapshot.roadmap_hash,
                        identified.snapshot.model_dump_json(),
                        identified.created_at.isoformat(),
                        identified.supersedes_id,
                        project_row_id,
                        identified.roadmap_snapshot_id,
                    ),
                )

                stored_records.append(
                    identified.model_copy(deep=True)
                )

            connection.execute("COMMIT")
            return stored_records
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
                "registry records."
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

    def load_by_snapshot_id(
        self,
        roadmap_snapshot_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        connection = self._connect()

        try:
            record = (
                self._load_by_snapshot_id_on_connection(
                    connection,
                    roadmap_snapshot_id.strip(),
                )
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
                "by durable snapshot ID."
            ) from error
        finally:
            connection.close()

    def load_by_durable_identity(
        self,
        *,
        project_id: str,
        roadmap_snapshot_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        connection = self._connect()

        try:
            record = (
                self._load_by_durable_identity_on_connection(
                    connection,
                    project_id=project_id.strip(),
                    roadmap_snapshot_id=(
                        roadmap_snapshot_id.strip()
                    ),
                )
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
                "by durable identity."
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
                    project.project_id,
                    roadmap.roadmap_snapshot_id,
                    roadmap.project_direction_id,
                    roadmap.response_direction_id,
                    roadmap.title,
                    roadmap.snapshot_json,
                    roadmap.created_at,
                    roadmap.supersedes_id
                FROM roadmap_registry AS roadmap
                LEFT JOIN projects AS project
                    ON project.project_row_id =
                        roadmap.project_row_id
                WHERE roadmap.workspace_id = ?
                ORDER BY
                    roadmap.created_at DESC,
                    roadmap.project_direction_id
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
                project.project_id,
                roadmap.roadmap_snapshot_id,
                roadmap.project_direction_id,
                roadmap.response_direction_id,
                roadmap.title,
                roadmap.snapshot_json,
                roadmap.created_at,
                roadmap.supersedes_id
            FROM roadmap_registry AS roadmap
            LEFT JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE
                roadmap.workspace_id = ?
                AND roadmap.project_direction_id = ?
            """,
            (
                self._workspace_id,
                project_direction_id,
            ),
        ).fetchone()

        if row is None:
            return None

        return self._record_from_row(row)

    def _load_by_snapshot_id_on_connection(
        self,
        connection: sqlite3.Connection,
        roadmap_snapshot_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        row = connection.execute(
            """
            SELECT
                project.project_id,
                roadmap.roadmap_snapshot_id,
                roadmap.project_direction_id,
                roadmap.response_direction_id,
                roadmap.title,
                roadmap.snapshot_json,
                roadmap.created_at,
                roadmap.supersedes_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE
                roadmap.workspace_id = ?
                AND roadmap.roadmap_snapshot_id = ?
            """,
            (
                self._workspace_id,
                roadmap_snapshot_id,
            ),
        ).fetchone()

        return (
            self._record_from_row(row)
            if row is not None
            else None
        )

    def _load_by_durable_identity_on_connection(
        self,
        connection: sqlite3.Connection,
        *,
        project_id: str,
        roadmap_snapshot_id: str,
    ) -> Optional[StoredRoadmapSnapshot]:
        row = connection.execute(
            """
            SELECT
                project.project_id,
                roadmap.roadmap_snapshot_id,
                roadmap.project_direction_id,
                roadmap.response_direction_id,
                roadmap.title,
                roadmap.snapshot_json,
                roadmap.created_at,
                roadmap.supersedes_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE
                roadmap.workspace_id = ?
                AND project.workspace_id = ?
                AND project.project_id = ?
                AND roadmap.roadmap_snapshot_id = ?
            """,
            (
                self._workspace_id,
                self._workspace_id,
                project_id,
                roadmap_snapshot_id,
            ),
        ).fetchone()

        return (
            self._record_from_row(row)
            if row is not None
            else None
        )

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
    ) -> StoredRoadmapSnapshot:
        project_direction_id = (
            row["project_direction_id"]
        )

        return StoredRoadmapSnapshot(
            project_id=(
                row["project_id"]
                or (
                    "proj_migrated_"
                    + project_direction_id
                )
            ),
            roadmap_snapshot_id=(
                row["roadmap_snapshot_id"]
                or (
                    "snap_migrated_"
                    + project_direction_id
                )
            ),
            project_direction_id=(
                project_direction_id
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

    @staticmethod
    def _identify_record(
        record: StoredRoadmapSnapshot,
    ) -> StoredRoadmapSnapshot:
        project_id = (
            record.project_id.strip()
            if record.project_id is not None
            else (
                "proj_migrated_"
                + record.project_direction_id
            )
        )
        roadmap_snapshot_id = (
            record.roadmap_snapshot_id.strip()
            if record.roadmap_snapshot_id is not None
            else (
                "snap_migrated_"
                + record.project_direction_id
            )
        )

        return record.model_copy(
            update={
                "project_id": project_id,
                "roadmap_snapshot_id": (
                    roadmap_snapshot_id
                ),
            },
            deep=True,
        )

    def _ensure_project_on_connection(
        self,
        connection: sqlite3.Connection,
        record: StoredRoadmapSnapshot,
    ) -> int:
        if record.project_id is None:
            raise RoadmapRegistryError(
                "Roadmap project identity is missing."
            )

        existing = connection.execute(
            """
            SELECT
                project_row_id,
                title
            FROM projects
            WHERE
                workspace_id = ?
                AND project_id = ?
            """,
            (
                self._workspace_id,
                record.project_id,
            ),
        ).fetchone()

        if existing is not None:
            return int(existing["project_row_id"])

        cursor = connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (
                record.project_id,
                self._workspace_id,
                record.title,
                record.created_at.isoformat(),
                record.created_at.isoformat(),
            ),
        )

        return int(cursor.lastrowid)

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
