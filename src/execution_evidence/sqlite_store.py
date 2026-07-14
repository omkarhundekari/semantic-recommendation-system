from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional, Sequence

from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.store import (
    RepositoryEvidenceConflictError,
    RepositoryEvidenceRestoreError,
    RepositoryEvidenceRestoreReport,
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
    build_repository_evidence_restore_report,
    prepare_repository_evidence_restore,
)


DEFAULT_WORKSPACE_ID = "local"


class SQLiteRepositoryEvidenceStoreError(
    RuntimeError
):
    pass


class SQLiteRepositoryEvidenceStore(
    RepositoryEvidenceStore
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

        self._ensure_workspace()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def load(
        self,
        repository_key: str,
    ) -> Optional[StoredRepositoryEvidence]:
        connection = self._connect()

        try:
            repository_row = connection.execute(
                """
                SELECT
                    repository_id,
                    provider,
                    owner,
                    repository_name,
                    canonical_url,
                    revision,
                    aggregate_schema_version,
                    saved_at
                FROM repositories
                WHERE
                    workspace_id = ?
                    AND repository_key = ?
                """,
                (
                    self._workspace_id,
                    repository_key,
                ),
            ).fetchone()

            if repository_row is None:
                return None

            repository_id = int(
                repository_row["repository_id"]
            )

            evidence = [
                ExecutionEvidenceItem.model_validate_json(
                    row["payload_json"]
                )
                for row in connection.execute(
                    """
                    SELECT payload_json
                    FROM evidence_items
                    WHERE repository_id = ?
                    ORDER BY position
                    """,
                    (repository_id,),
                )
            ]

            attributions = [
                EvidenceAttribution.model_validate_json(
                    row["payload_json"]
                )
                for row in connection.execute(
                    """
                    SELECT payload_json
                    FROM evidence_attributions
                    WHERE repository_id = ?
                    ORDER BY position
                    """,
                    (repository_id,),
                )
            ]

            sync_state_row = connection.execute(
                """
                SELECT payload_json
                FROM repository_sync_states
                WHERE repository_id = ?
                """,
                (repository_id,),
            ).fetchone()

            sync_snapshot_row = connection.execute(
                """
                SELECT payload_json
                FROM repository_sync_snapshots
                WHERE repository_id = ?
                """,
                (repository_id,),
            ).fetchone()

            if (
                sync_state_row is None
                or sync_snapshot_row is None
            ):
                raise SQLiteRepositoryEvidenceStoreError(
                    "SQLite repository evidence aggregate "
                    "is incomplete."
                )

            return StoredRepositoryEvidence(
                schema_version=int(
                    repository_row[
                        "aggregate_schema_version"
                    ]
                ),
                repository={
                    "provider": repository_row[
                        "provider"
                    ],
                    "owner": repository_row["owner"],
                    "repository": repository_row[
                        "repository_name"
                    ],
                    "canonical_url": repository_row[
                        "canonical_url"
                    ],
                },
                evidence=evidence,
                attributions=attributions,
                sync_state=(
                    RepositorySyncState.model_validate_json(
                        sync_state_row["payload_json"]
                    )
                ),
                sync_snapshot=(
                    GitHubRepositorySyncSnapshot
                    .model_validate_json(
                        sync_snapshot_row[
                            "payload_json"
                        ]
                    )
                ),
                revision=int(
                    repository_row["revision"]
                ),
                saved_at=repository_row["saved_at"],
            )
        except SQLiteRepositoryEvidenceStoreError:
            raise
        except (
            sqlite3.Error,
            ValueError,
        ) as error:
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not load SQLite repository evidence."
            ) from error
        finally:
            connection.close()

    def save(
        self,
        record: StoredRepositoryEvidence,
        *,
        expected_revision: Optional[int] = None,
    ) -> StoredRepositoryEvidence:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            self._ensure_workspace_on_connection(
                connection
            )

            repository_key = (
                record.repository.repository_key
            )

            existing = connection.execute(
                """
                SELECT repository_id, revision
                FROM repositories
                WHERE
                    workspace_id = ?
                    AND repository_key = ?
                """,
                (
                    self._workspace_id,
                    repository_key,
                ),
            ).fetchone()

            current_revision = (
                int(existing["revision"])
                if existing is not None
                else -1
            )

            if (
                expected_revision is not None
                and expected_revision
                != current_revision
            ):
                raise RepositoryEvidenceConflictError(
                    "Repository evidence revision "
                    "conflict: "
                    f"expected {expected_revision}, "
                    f"found {current_revision}."
                )

            next_revision = current_revision + 1
            timestamp = record.saved_at.isoformat()

            if existing is None:
                cursor = connection.execute(
                    """
                    INSERT INTO repositories (
                        workspace_id,
                        repository_key,
                        provider,
                        owner,
                        repository_name,
                        canonical_url,
                        revision,
                        aggregate_schema_version,
                        saved_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    (
                        self._workspace_id,
                        repository_key,
                        record.repository.provider,
                        record.repository.owner,
                        record.repository.repository,
                        record.repository.canonical_url,
                        next_revision,
                        record.schema_version,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
                repository_id = int(
                    cursor.lastrowid
                )
            else:
                repository_id = int(
                    existing["repository_id"]
                )

                connection.execute(
                    """
                    UPDATE repositories
                    SET
                        provider = ?,
                        owner = ?,
                        repository_name = ?,
                        canonical_url = ?,
                        revision = ?,
                        aggregate_schema_version = ?,
                        saved_at = ?,
                        updated_at = ?
                    WHERE repository_id = ?
                    """,
                    (
                        record.repository.provider,
                        record.repository.owner,
                        record.repository.repository,
                        record.repository.canonical_url,
                        next_revision,
                        record.schema_version,
                        timestamp,
                        timestamp,
                        repository_id,
                    ),
                )

                connection.execute(
                    """
                    DELETE FROM evidence_attributions
                    WHERE repository_id = ?
                    """,
                    (repository_id,),
                )
                connection.execute(
                    """
                    DELETE FROM evidence_items
                    WHERE repository_id = ?
                    """,
                    (repository_id,),
                )

            self._write_evidence(
                connection,
                repository_id,
                record.evidence,
            )
            self._write_attributions(
                connection,
                repository_id,
                record.attributions,
            )

            connection.execute(
                """
                INSERT INTO repository_sync_states (
                    repository_id,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(repository_id)
                DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    repository_id,
                    record.sync_state.model_dump_json(),
                    timestamp,
                ),
            )

            connection.execute(
                """
                INSERT INTO repository_sync_snapshots (
                    repository_id,
                    payload_json,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(repository_id)
                DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (
                    repository_id,
                    record.sync_snapshot.model_dump_json(),
                    timestamp,
                ),
            )

            connection.execute("COMMIT")

            return record.model_copy(
                update={
                    "revision": next_revision,
                },
                deep=True,
            )
        except RepositoryEvidenceConflictError:
            self._rollback(connection)
            raise
        except sqlite3.Error as error:
            self._rollback(connection)
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not save SQLite repository evidence."
            ) from error
        finally:
            connection.close()

    def restore(
        self,
        records: Sequence[
            StoredRepositoryEvidence
        ],
        *,
        require_empty: bool = True,
    ) -> RepositoryEvidenceRestoreReport:
        prepared = (
            prepare_repository_evidence_restore(
                records
            )
        )
        connection = self._connect()

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )
            self._ensure_workspace_on_connection(
                connection
            )

            existing_keys = {
                str(row["repository_key"])
                for row in connection.execute(
                    """
                    SELECT repository_key
                    FROM repositories
                    WHERE workspace_id = ?
                    """,
                    (self._workspace_id,),
                )
            }

            if require_empty and existing_keys:
                raise RepositoryEvidenceRestoreError(
                    "Repository evidence restore requires "
                    "an empty destination."
                )

            restored_keys = {
                record.repository.repository_key
                for record in prepared
            }
            conflicting_keys = sorted(
                restored_keys.intersection(
                    existing_keys
                )
            )

            if conflicting_keys:
                raise RepositoryEvidenceRestoreError(
                    "Repository evidence restore would "
                    "overwrite existing repositories: "
                    + ", ".join(conflicting_keys)
                    + "."
                )

            for record in prepared:
                self._restore_record_on_connection(
                    connection,
                    record,
                )

            connection.execute("COMMIT")

            return (
                build_repository_evidence_restore_report(
                    prepared
                )
            )
        except RepositoryEvidenceRestoreError:
            self._rollback(connection)
            raise
        except sqlite3.Error as error:
            self._rollback(connection)
            raise RepositoryEvidenceRestoreError(
                "Could not restore repository evidence "
                "into SQLite."
            ) from error
        finally:
            connection.close()

    def delete(
        self,
        repository_key: str,
    ) -> bool:
        connection = self._connect()

        try:
            connection.execute("BEGIN IMMEDIATE")

            cursor = connection.execute(
                """
                DELETE FROM repositories
                WHERE
                    workspace_id = ?
                    AND repository_key = ?
                """,
                (
                    self._workspace_id,
                    repository_key,
                ),
            )

            removed = cursor.rowcount > 0
            connection.execute("COMMIT")

            return removed
        except sqlite3.Error as error:
            self._rollback(connection)
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not delete SQLite repository evidence."
            ) from error
        finally:
            connection.close()

    def list_repository_keys(self) -> List[str]:
        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT repository_key
                FROM repositories
                WHERE workspace_id = ?
                ORDER BY repository_key
                """,
                (self._workspace_id,),
            )

            return [
                str(row["repository_key"])
                for row in rows
            ]
        except sqlite3.Error as error:
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not list SQLite repositories."
            ) from error
        finally:
            connection.close()

    def _restore_record_on_connection(
        self,
        connection: sqlite3.Connection,
        record: StoredRepositoryEvidence,
    ) -> None:
        timestamp = record.saved_at.isoformat()
        repository_key = (
            record.repository.repository_key
        )

        cursor = connection.execute(
            """
            INSERT INTO repositories (
                workspace_id,
                repository_key,
                provider,
                owner,
                repository_name,
                canonical_url,
                revision,
                aggregate_schema_version,
                saved_at,
                created_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                self._workspace_id,
                repository_key,
                record.repository.provider,
                record.repository.owner,
                record.repository.repository,
                record.repository.canonical_url,
                record.revision,
                record.schema_version,
                timestamp,
                timestamp,
                timestamp,
            ),
        )
        repository_id = int(cursor.lastrowid)

        self._write_evidence(
            connection,
            repository_id,
            record.evidence,
        )
        self._write_attributions(
            connection,
            repository_id,
            record.attributions,
        )

        connection.execute(
            """
            INSERT INTO repository_sync_states (
                repository_id,
                payload_json,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                repository_id,
                record.sync_state.model_dump_json(),
                timestamp,
            ),
        )

        connection.execute(
            """
            INSERT INTO repository_sync_snapshots (
                repository_id,
                payload_json,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                repository_id,
                record.sync_snapshot.model_dump_json(),
                timestamp,
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        try:
            return connect_execution_evidence_database(
                self._path
            )
        except Exception as error:
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not connect to SQLite repository "
                "evidence storage."
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
            raise SQLiteRepositoryEvidenceStoreError(
                "Could not initialize SQLite workspace."
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

    def _write_evidence(
        self,
        connection: sqlite3.Connection,
        repository_id: int,
        evidence: List[ExecutionEvidenceItem],
    ) -> None:
        for position, item in enumerate(evidence):
            connection.execute(
                """
                INSERT INTO evidence_items (
                    repository_id,
                    evidence_key,
                    evidence_type,
                    external_id,
                    title,
                    description,
                    url,
                    occurred_at,
                    first_seen_at,
                    last_seen_at,
                    content_hash,
                    payload_json,
                    position
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    repository_id,
                    item.evidence_key,
                    item.evidence_type,
                    item.external_id,
                    item.title,
                    item.description,
                    item.url,
                    item.occurred_at.isoformat(),
                    item.first_seen_at.isoformat(),
                    item.last_seen_at.isoformat(),
                    None,
                    item.model_dump_json(),
                    position,
                ),
            )

    def _write_attributions(
        self,
        connection: sqlite3.Connection,
        repository_id: int,
        attributions: List[EvidenceAttribution],
    ) -> None:
        for position, attribution in enumerate(
            attributions
        ):
            connection.execute(
                """
                INSERT INTO evidence_attributions (
                    repository_id,
                    evidence_key,
                    roadmap_node_id,
                    source,
                    confidence,
                    rationale,
                    status,
                    decided_at,
                    payload_json,
                    position
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    repository_id,
                    attribution.evidence_key,
                    attribution.roadmap_node_id,
                    attribution.source,
                    attribution.confidence,
                    attribution.rationale,
                    attribution.status,
                    (
                        attribution.decided_at.isoformat()
                        if attribution.decided_at
                        is not None
                        else None
                    ),
                    attribution.model_dump_json(),
                    position,
                ),
            )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass
