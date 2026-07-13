from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Sequence
from uuid import uuid4

from pydantic import BaseModel, Field

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.store import (
    RepositoryEvidenceStore,
    StoredRepositoryEvidence,
)


CANONICAL_AGGREGATE_VERSION = 1


class RepositoryEvidenceMigrationError(
    RuntimeError
):
    pass


class RepositoryEvidenceRecordDigest(BaseModel):
    repository_key: str
    aggregate_hash: str
    revision: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    attribution_count: int = Field(ge=0)


class RepositoryEvidenceMigrationReport(BaseModel):
    report_version: int = 1
    canonicalization_version: int = (
        CANONICAL_AGGREGATE_VERSION
    )
    source_type: str
    destination_type: str = "sqlite"
    repository_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    attribution_count: int = Field(ge=0)
    root_hash: str
    records: List[
        RepositoryEvidenceRecordDigest
    ] = Field(default_factory=list)
    integrity_check: str
    foreign_key_violation_count: int = Field(
        ge=0
    )
    relational_counts: Dict[str, int] = Field(
        default_factory=dict
    )
    verified: bool
    dry_run: bool = True


def canonical_repository_evidence_payload(
    record: StoredRepositoryEvidence,
) -> bytes:
    payload = {
        "canonicalization_version": (
            CANONICAL_AGGREGATE_VERSION
        ),
        "aggregate": record.model_dump(
            mode="json",
        ),
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return serialized.encode("utf-8")


def hash_repository_evidence(
    record: StoredRepositoryEvidence,
) -> str:
    return hashlib.sha256(
        canonical_repository_evidence_payload(
            record
        )
    ).hexdigest()


def build_repository_evidence_root_hash(
    records: Sequence[
        StoredRepositoryEvidence
    ],
) -> str:
    entries = sorted(
        (
            record.repository.repository_key,
            hash_repository_evidence(record),
        )
        for record in records
    )

    serialized = json.dumps(
        entries,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def load_repository_evidence_snapshot(
    store: RepositoryEvidenceStore,
) -> List[StoredRepositoryEvidence]:
    records: List[
        StoredRepositoryEvidence
    ] = []

    for repository_key in sorted(
        store.list_repository_keys()
    ):
        record = store.load(repository_key)

        if record is None:
            raise RepositoryEvidenceMigrationError(
                "Repository evidence disappeared "
                "while creating the migration snapshot: "
                f"{repository_key}."
            )

        records.append(record)

    return records


def verify_repository_evidence_migration(
    *,
    source_records: Sequence[
        StoredRepositoryEvidence
    ],
    destination: SQLiteRepositoryEvidenceStore,
) -> RepositoryEvidenceMigrationReport:
    source_by_key = {
        record.repository.repository_key: record
        for record in source_records
    }
    source_keys = sorted(source_by_key)
    destination_keys = (
        destination.list_repository_keys()
    )

    if destination_keys != source_keys:
        raise RepositoryEvidenceMigrationError(
            "Destination repository keys do not "
            "match the source snapshot."
        )

    destination_records: List[
        StoredRepositoryEvidence
    ] = []

    for repository_key in source_keys:
        destination_record = destination.load(
            repository_key
        )

        if destination_record is None:
            raise RepositoryEvidenceMigrationError(
                "Destination repository evidence "
                f"is missing: {repository_key}."
            )

        source_record = source_by_key[
            repository_key
        ]

        if destination_record != source_record:
            raise RepositoryEvidenceMigrationError(
                "Destination aggregate does not "
                "match the source aggregate: "
                f"{repository_key}."
            )

        source_hash = hash_repository_evidence(
            source_record
        )
        destination_hash = (
            hash_repository_evidence(
                destination_record
            )
        )

        if destination_hash != source_hash:
            raise RepositoryEvidenceMigrationError(
                "Destination aggregate hash does "
                "not match the source aggregate: "
                f"{repository_key}."
            )

        destination_records.append(
            destination_record
        )

    connection = (
        connect_execution_evidence_database(
            destination.path
        )
    )

    try:
        integrity_rows = connection.execute(
            "PRAGMA integrity_check"
        ).fetchall()
        integrity_messages = [
            str(row[0])
            for row in integrity_rows
        ]
        integrity_check = ",".join(
            integrity_messages
        )

        if integrity_messages != ["ok"]:
            raise RepositoryEvidenceMigrationError(
                "SQLite integrity check failed: "
                + integrity_check
            )

        foreign_key_rows = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_rows:
            raise RepositoryEvidenceMigrationError(
                "SQLite foreign key check reported "
                "violations."
            )

        relational_counts = {
            table_name: int(
                connection.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM {table_name}
                    """
                ).fetchone()["count"]
            )
            for table_name in (
                "repositories",
                "evidence_items",
                "evidence_attributions",
                "repository_sync_states",
                "repository_sync_snapshots",
            )
        }

        expected_counts = {
            "repositories": len(
                source_records
            ),
            "evidence_items": sum(
                len(record.evidence)
                for record in source_records
            ),
            "evidence_attributions": sum(
                len(record.attributions)
                for record in source_records
            ),
            "repository_sync_states": len(
                source_records
            ),
            "repository_sync_snapshots": len(
                source_records
            ),
        }

        if relational_counts != expected_counts:
            raise RepositoryEvidenceMigrationError(
                "SQLite relational row counts do "
                "not match the source aggregates."
            )

        _verify_stored_sequences(
            connection=connection,
            source_records=source_records,
        )
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not verify the SQLite "
            "migration database."
        ) from error
    finally:
        connection.close()

    source_root_hash = (
        build_repository_evidence_root_hash(
            source_records
        )
    )
    destination_root_hash = (
        build_repository_evidence_root_hash(
            destination_records
        )
    )

    if destination_root_hash != source_root_hash:
        raise RepositoryEvidenceMigrationError(
            "Destination root hash does not "
            "match the source snapshot."
        )

    record_digests = [
        RepositoryEvidenceRecordDigest(
            repository_key=(
                record.repository.repository_key
            ),
            aggregate_hash=(
                hash_repository_evidence(record)
            ),
            revision=record.revision,
            evidence_count=len(
                record.evidence
            ),
            attribution_count=len(
                record.attributions
            ),
        )
        for record in sorted(
            source_records,
            key=lambda item: (
                item.repository.repository_key
            ),
        )
    ]

    return RepositoryEvidenceMigrationReport(
        source_type=(
            source_records.__class__.__name__
        ),
        repository_count=len(
            source_records
        ),
        evidence_count=sum(
            len(record.evidence)
            for record in source_records
        ),
        attribution_count=sum(
            len(record.attributions)
            for record in source_records
        ),
        root_hash=source_root_hash,
        records=record_digests,
        integrity_check="ok",
        foreign_key_violation_count=0,
        relational_counts=relational_counts,
        verified=True,
        dry_run=True,
    )


def dry_run_repository_evidence_migration(
    *,
    source: RepositoryEvidenceStore,
    destination_directory: Path | str,
) -> RepositoryEvidenceMigrationReport:
    source_records = (
        load_repository_evidence_snapshot(
            source
        )
    )

    directory = Path(
        destination_directory
    )
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = directory / (
        ".solvyn-execution-evidence-"
        f"{uuid4().hex}.migrating.db"
    )

    try:
        destination = (
            SQLiteRepositoryEvidenceStore(
                temporary_path
            )
        )
        destination.restore(
            source_records,
            require_empty=True,
        )

        del destination

        cold_destination = (
            SQLiteRepositoryEvidenceStore(
                temporary_path
            )
        )

        return (
            verify_repository_evidence_migration(
                source_records=source_records,
                destination=cold_destination,
            )
        )
    finally:
        remove_sqlite_database_artifacts(
            temporary_path
        )


def remove_sqlite_database_artifacts(
    database_path: Path | str,
) -> None:
    path = Path(database_path)

    artifact_paths = (
        path,
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    )

    errors = []

    for artifact_path in artifact_paths:
        try:
            artifact_path.unlink(
                missing_ok=True
            )
        except OSError as error:
            errors.append(
                (
                    artifact_path,
                    error,
                )
            )

    if errors:
        raise RepositoryEvidenceMigrationError(
            "Could not remove disposable SQLite "
            "migration artifacts."
        )


def _verify_stored_sequences(
    *,
    connection: sqlite3.Connection,
    source_records: Sequence[
        StoredRepositoryEvidence
    ],
) -> None:
    for record in source_records:
        repository_row = connection.execute(
            """
            SELECT repository_id
            FROM repositories
            WHERE
                workspace_id = ?
                AND repository_key = ?
            """,
            (
                "local",
                record.repository.repository_key,
            ),
        ).fetchone()

        if repository_row is None:
            raise RepositoryEvidenceMigrationError(
                "Could not verify repository "
                "sequence storage."
            )

        repository_id = int(
            repository_row["repository_id"]
        )

        evidence_keys = [
            str(row["evidence_key"])
            for row in connection.execute(
                """
                SELECT evidence_key
                FROM evidence_items
                WHERE repository_id = ?
                ORDER BY position
                """,
                (repository_id,),
            )
        ]

        expected_evidence_keys = [
            item.evidence_key
            for item in record.evidence
        ]

        if evidence_keys != expected_evidence_keys:
            raise RepositoryEvidenceMigrationError(
                "SQLite evidence ordering does "
                "not match the source aggregate: "
                f"{record.repository.repository_key}."
            )

        attribution_keys = [
            (
                str(row["evidence_key"]),
                str(row["roadmap_node_id"]),
            )
            for row in connection.execute(
                """
                SELECT
                    evidence_key,
                    roadmap_node_id
                FROM evidence_attributions
                WHERE repository_id = ?
                ORDER BY position
                """,
                (repository_id,),
            )
        ]

        expected_attribution_keys = [
            (
                attribution.evidence_key,
                attribution.roadmap_node_id,
            )
            for attribution in (
                record.attributions
            )
        ]

        if (
            attribution_keys
            != expected_attribution_keys
        ):
            raise RepositoryEvidenceMigrationError(
                "SQLite attribution ordering does "
                "not match the source aggregate: "
                f"{record.repository.repository_key}."
            )


MIGRATION_RECEIPT_VERSION = 1


class RepositoryEvidenceMigrationReceipt(
    BaseModel
):
    receipt_version: int = (
        MIGRATION_RECEIPT_VERSION
    )
    receipt_id: str
    source_type: str
    source_identifier: str
    source_root_hash: str
    canonicalization_version: int
    report_version: int
    repository_count: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    attribution_count: int = Field(ge=0)
    deterministic_report_json: str
    created_at: str


def deterministic_migration_report_json(
    report: RepositoryEvidenceMigrationReport,
) -> str:
    return json.dumps(
        report.model_dump(
            mode="json",
        ),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_migration_receipt(
    *,
    report: RepositoryEvidenceMigrationReport,
    source_identifier: str,
    created_at: str,
) -> RepositoryEvidenceMigrationReceipt:
    deterministic_report = (
        deterministic_migration_report_json(
            report
        )
    )

    receipt_material = json.dumps(
        {
            "receipt_version": (
                MIGRATION_RECEIPT_VERSION
            ),
            "source_type": report.source_type,
            "source_identifier": (
                source_identifier
            ),
            "source_root_hash": (
                report.root_hash
            ),
            "canonicalization_version": (
                report.canonicalization_version
            ),
            "report_version": (
                report.report_version
            ),
            "deterministic_report_json": (
                deterministic_report
            ),
        },
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    receipt_id = hashlib.sha256(
        receipt_material.encode("utf-8")
    ).hexdigest()

    return RepositoryEvidenceMigrationReceipt(
        receipt_id=receipt_id,
        source_type=report.source_type,
        source_identifier=source_identifier,
        source_root_hash=report.root_hash,
        canonicalization_version=(
            report.canonicalization_version
        ),
        report_version=report.report_version,
        repository_count=(
            report.repository_count
        ),
        evidence_count=report.evidence_count,
        attribution_count=(
            report.attribution_count
        ),
        deterministic_report_json=(
            deterministic_report
        ),
        created_at=created_at,
    )


def persist_migration_receipt(
    *,
    database_path: Path | str,
    receipt: RepositoryEvidenceMigrationReceipt,
) -> None:
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )
        connection.execute(
            """
            INSERT INTO execution_evidence_import_receipts (
                receipt_id,
                source_type,
                source_identifier,
                source_root_hash,
                canonicalization_version,
                report_version,
                repository_count,
                evidence_count,
                attribution_count,
                deterministic_report_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.source_type,
                receipt.source_identifier,
                receipt.source_root_hash,
                receipt.canonicalization_version,
                receipt.report_version,
                receipt.repository_count,
                receipt.evidence_count,
                receipt.attribution_count,
                receipt.deterministic_report_json,
                receipt.created_at,
            ),
        )
        connection.execute("COMMIT")
    except sqlite3.Error as error:
        try:
            connection.execute(
                "ROLLBACK"
            )
        except sqlite3.Error:
            pass

        raise RepositoryEvidenceMigrationError(
            "Could not persist the SQLite "
            "migration receipt."
        ) from error
    finally:
        connection.close()


def verify_migration_receipt(
    *,
    database_path: Path | str,
    receipt: RepositoryEvidenceMigrationReceipt,
) -> None:
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT
                receipt_id,
                source_type,
                source_identifier,
                source_root_hash,
                canonicalization_version,
                report_version,
                repository_count,
                evidence_count,
                attribution_count,
                deterministic_report_json,
                created_at
            FROM execution_evidence_import_receipts
            WHERE receipt_id = ?
            """,
            (receipt.receipt_id,),
        ).fetchone()
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not verify the SQLite "
            "migration receipt."
        ) from error
    finally:
        connection.close()

    if row is None:
        raise RepositoryEvidenceMigrationError(
            "SQLite migration receipt is missing."
        )

    stored = (
        RepositoryEvidenceMigrationReceipt(
            **dict(row)
        )
    )

    if stored != receipt:
        raise RepositoryEvidenceMigrationError(
            "SQLite migration receipt does not "
            "match the expected receipt."
        )


def assert_destination_artifacts_absent(
    database_path: Path | str,
) -> None:
    path = Path(database_path)

    artifact_paths = (
        path,
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    )

    existing = [
        artifact
        for artifact in artifact_paths
        if artifact.exists()
    ]

    if existing:
        raise RepositoryEvidenceMigrationError(
            "Destination SQLite artifacts already "
            "exist: "
            + ", ".join(
                str(artifact)
                for artifact in existing
            )
            + "."
        )


class RepositoryEvidenceMigrationLock:
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)
        self._descriptor = None

    def __enter__(
        self,
    ) -> "RepositoryEvidenceMigrationLock":
        import os

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            self._descriptor = os.open(
                str(self._path),
                os.O_CREAT
                | os.O_EXCL
                | os.O_WRONLY,
                0o600,
            )
            os.write(
                self._descriptor,
                (
                    f"pid={os.getpid()}\n"
                ).encode("utf-8"),
            )
            os.fsync(self._descriptor)
        except FileExistsError as error:
            raise RepositoryEvidenceMigrationError(
                "Another execution evidence "
                "migration appears to be running."
            ) from error
        except OSError as error:
            raise RepositoryEvidenceMigrationError(
                "Could not acquire the execution "
                "evidence migration lock."
            ) from error

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        import os

        if self._descriptor is not None:
            try:
                os.close(self._descriptor)
            finally:
                self._descriptor = None

        try:
            self._path.unlink(
                missing_ok=True
            )
        except OSError as error:
            if exc_value is None:
                raise (
                    RepositoryEvidenceMigrationError(
                        "Could not remove the execution "
                        "evidence migration lock."
                    )
                ) from error


def write_migration_report_atomically(
    *,
    report_path: Path | str,
    report: RepositoryEvidenceMigrationReport,
) -> None:
    import os

    path = Path(report_path)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        f".{path.name}.{uuid4().hex}.tmp"
    )

    serialized = json.dumps(
        report.model_dump(
            mode="json",
        ),
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )

    try:
        with temporary_path.open(
            "w",
            encoding="utf-8",
        ) as temporary_file:
            temporary_file.write(serialized)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(
                temporary_file.fileno()
            )

        os.replace(
            temporary_path,
            path,
        )

        directory_descriptor = os.open(
            str(path.parent),
            os.O_RDONLY,
        )

        try:
            os.fsync(
                directory_descriptor
            )
        finally:
            os.close(
                directory_descriptor
            )
    except OSError as error:
        try:
            temporary_path.unlink(
                missing_ok=True
            )
        except OSError:
            pass

        raise RepositoryEvidenceMigrationError(
            "Could not write the execution "
            "evidence migration report."
        ) from error


def _temporary_migration_database_path(
    destination_path: Path,
) -> Path:
    return destination_path.parent / (
        f".{destination_path.name}."
        f"{uuid4().hex}.migrating"
    )


def _build_verified_json_migration_database(
    *,
    source_path: Path,
    temporary_path: Path,
    created_at: str,
    dry_run: bool,
) -> RepositoryEvidenceMigrationReport:
    from execution_evidence.json_store import (
        JsonRepositoryEvidenceStore,
    )

    source = JsonRepositoryEvidenceStore(
        source_path
    )
    source_records = (
        load_repository_evidence_snapshot(
            source
        )
    )
    initial_root_hash = (
        build_repository_evidence_root_hash(
            source_records
        )
    )

    temporary_store = (
        SQLiteRepositoryEvidenceStore(
            temporary_path
        )
    )
    temporary_store.restore(
        source_records,
        require_empty=True,
    )

    del temporary_store

    cold_store = (
        SQLiteRepositoryEvidenceStore(
            temporary_path
        )
    )

    report = (
        verify_repository_evidence_migration(
            source_records=source_records,
            destination=cold_store,
        )
    ).model_copy(
        update={
            "source_type": "json",
            "dry_run": dry_run,
        },
        deep=True,
    )

    del cold_store

    receipt = build_migration_receipt(
        report=report,
        source_identifier=str(
            source_path
        ),
        created_at=created_at,
    )
    persist_migration_receipt(
        database_path=temporary_path,
        receipt=receipt,
    )
    verify_migration_receipt(
        database_path=temporary_path,
        receipt=receipt,
    )

    final_source_records = (
        load_repository_evidence_snapshot(
            JsonRepositoryEvidenceStore(
                source_path
            )
        )
    )
    final_root_hash = (
        build_repository_evidence_root_hash(
            final_source_records
        )
    )

    if final_root_hash != initial_root_hash:
        raise RepositoryEvidenceMigrationError(
            "JSON source changed during "
            "the migration."
        )

    return report


def _sqlite_sidecar_paths(
    database_path: Path | str,
) -> tuple[Path, Path, Path]:
    path = Path(database_path)

    return (
        Path(f"{path}-wal"),
        Path(f"{path}-shm"),
        Path(f"{path}-journal"),
    )


def finalize_sqlite_database_for_promotion(
    database_path: Path | str,
) -> None:
    path = Path(database_path)

    try:
        connection = sqlite3.connect(
            str(path),
            timeout=5.0,
            isolation_level=None,
        )
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not open the verified SQLite "
            "database for promotion."
        ) from error

    try:
        checkpoint = connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()

        if checkpoint is None:
            raise RepositoryEvidenceMigrationError(
                "SQLite WAL checkpoint returned "
                "no result."
            )

        busy_count = int(checkpoint[0])

        if busy_count != 0:
            raise RepositoryEvidenceMigrationError(
                "SQLite WAL checkpoint could not "
                "complete because the database is busy."
            )

        journal_mode_row = connection.execute(
            "PRAGMA journal_mode = DELETE"
        ).fetchone()

        if (
            journal_mode_row is None
            or str(
                journal_mode_row[0]
            ).lower()
            != "delete"
        ):
            raise RepositoryEvidenceMigrationError(
                "Could not convert the migration "
                "database to single-file journal mode."
            )
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not finalize the SQLite "
            "migration database."
        ) from error
    finally:
        connection.close()

    wal_path, shm_path, journal_path = (
        _sqlite_sidecar_paths(path)
    )

    for durable_sidecar in (
        wal_path,
        journal_path,
    ):
        if (
            durable_sidecar.exists()
            and durable_sidecar.stat().st_size > 0
        ):
            raise RepositoryEvidenceMigrationError(
                "SQLite migration database still "
                "contains durable sidecar content "
                "after finalization: "
                f"{durable_sidecar}."
            )

    for removable_sidecar in (
        wal_path,
        shm_path,
        journal_path,
    ):
        try:
            removable_sidecar.unlink(
                missing_ok=True
            )
        except OSError as error:
            raise RepositoryEvidenceMigrationError(
                "Could not remove finalized SQLite "
                "sidecar file: "
                f"{removable_sidecar}."
            ) from error

    remaining_sidecars = [
        artifact
        for artifact in _sqlite_sidecar_paths(
            path
        )
        if artifact.exists()
    ]

    if remaining_sidecars:
        raise RepositoryEvidenceMigrationError(
            "SQLite migration database still has "
            "sidecar files after cleanup: "
            + ", ".join(
                str(artifact)
                for artifact in remaining_sidecars
            )
            + "."
        )


def verify_finalized_migration_database(
    *,
    database_path: Path | str,
) -> None:
    path = Path(database_path)
    uri = (
        path.resolve().as_uri()
        + "?mode=ro"
    )

    try:
        connection = sqlite3.connect(
            uri,
            uri=True,
            timeout=5.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not open the finalized SQLite "
            "database in read-only mode."
        ) from error

    try:
        integrity_messages = [
            str(row[0])
            for row in connection.execute(
                "PRAGMA integrity_check"
            ).fetchall()
        ]

        if integrity_messages != ["ok"]:
            raise RepositoryEvidenceMigrationError(
                "Finalized SQLite integrity check "
                "failed: "
                + ",".join(
                    integrity_messages
                )
            )

        foreign_key_rows = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_key_rows:
            raise RepositoryEvidenceMigrationError(
                "Finalized SQLite database contains "
                "foreign-key violations."
            )

        receipt_count = int(
            connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM execution_evidence_import_receipts
                """
            ).fetchone()["count"]
        )

        if receipt_count != 1:
            raise RepositoryEvidenceMigrationError(
                "Finalized SQLite database must "
                "contain exactly one migration receipt."
            )
    except sqlite3.Error as error:
        raise RepositoryEvidenceMigrationError(
            "Could not verify the finalized SQLite "
            "migration database."
        ) from error
    finally:
        connection.close()


def fsync_file(
    path: Path | str,
) -> None:
    import os

    file_path = Path(path)

    try:
        descriptor = os.open(
            str(file_path),
            os.O_RDONLY,
        )

        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise RepositoryEvidenceMigrationError(
            "Could not fsync the SQLite "
            "migration database."
        ) from error


def fsync_directory(
    path: Path | str,
) -> None:
    import os

    directory = Path(path)

    try:
        descriptor = os.open(
            str(directory),
            os.O_RDONLY,
        )

        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as error:
        raise RepositoryEvidenceMigrationError(
            "Could not fsync the migration "
            "destination directory."
        ) from error


def promote_sqlite_database_atomically(
    *,
    temporary_path: Path | str,
    destination_path: Path | str,
) -> None:
    import os

    temporary = Path(temporary_path)
    destination = Path(destination_path)

    if (
        temporary.resolve().parent
        != destination.resolve().parent
    ):
        raise RepositoryEvidenceMigrationError(
            "SQLite migration database must be "
            "created in the destination directory."
        )

    assert_destination_artifacts_absent(
        destination
    )
    fsync_file(temporary)

    try:
        os.replace(
            temporary,
            destination,
        )
    except OSError as error:
        raise RepositoryEvidenceMigrationError(
            "Could not atomically promote the "
            "SQLite migration database."
        ) from error

    fsync_directory(
        destination.parent
    )


def dry_run_json_to_sqlite_migration(
    *,
    source_path: Path | str,
    destination_path: Path | str,
    report_path: Path | str,
    created_at: str,
) -> RepositoryEvidenceMigrationReport:
    source_file = Path(source_path)
    destination_file = Path(
        destination_path
    )
    report_file = Path(report_path)
    lock_path = destination_file.with_name(
        f".{destination_file.name}.migration.lock"
    )

    assert_destination_artifacts_absent(
        destination_file
    )

    with RepositoryEvidenceMigrationLock(
        lock_path
    ):
        destination_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path = (
            _temporary_migration_database_path(
                destination_file
            )
        )

        try:
            report = (
                _build_verified_json_migration_database(
                    source_path=source_file,
                    temporary_path=temporary_path,
                    created_at=created_at,
                    dry_run=True,
                )
            )

            write_migration_report_atomically(
                report_path=report_file,
                report=report,
            )

            return report
        finally:
            remove_sqlite_database_artifacts(
                temporary_path
            )


def promote_json_to_sqlite_migration(
    *,
    source_path: Path | str,
    destination_path: Path | str,
    report_path: Path | str,
    created_at: str,
) -> RepositoryEvidenceMigrationReport:
    from execution_evidence.json_store import (
        JsonRepositoryEvidenceStore,
    )

    source_file = Path(source_path)
    destination_file = Path(
        destination_path
    )
    report_file = Path(report_path)
    lock_path = destination_file.with_name(
        f".{destination_file.name}.migration.lock"
    )

    assert_destination_artifacts_absent(
        destination_file
    )

    with RepositoryEvidenceMigrationLock(
        lock_path
    ):
        destination_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temporary_path = (
            _temporary_migration_database_path(
                destination_file
            )
        )
        promoted = False

        try:
            report = (
                _build_verified_json_migration_database(
                    source_path=source_file,
                    temporary_path=temporary_path,
                    created_at=created_at,
                    dry_run=False,
                )
            )

            finalize_sqlite_database_for_promotion(
                temporary_path
            )
            verify_finalized_migration_database(
                database_path=temporary_path
            )

            final_source_records = (
                load_repository_evidence_snapshot(
                    JsonRepositoryEvidenceStore(
                        source_file
                    )
                )
            )
            final_root_hash = (
                build_repository_evidence_root_hash(
                    final_source_records
                )
            )

            if final_root_hash != report.root_hash:
                raise RepositoryEvidenceMigrationError(
                    "JSON source changed immediately "
                    "before SQLite promotion."
                )

            promote_sqlite_database_atomically(
                temporary_path=temporary_path,
                destination_path=destination_file,
            )
            promoted = True

            verify_finalized_migration_database(
                database_path=destination_file
            )

            remaining_sidecars = [
                artifact
                for artifact in _sqlite_sidecar_paths(
                    destination_file
                )
                if artifact.exists()
            ]

            if remaining_sidecars:
                raise RepositoryEvidenceMigrationError(
                    "Promoted SQLite database created "
                    "unexpected sidecar files."
                )

            write_migration_report_atomically(
                report_path=report_file,
                report=report,
            )

            return report
        finally:
            if not promoted:
                remove_sqlite_database_artifacts(
                    temporary_path
                )
