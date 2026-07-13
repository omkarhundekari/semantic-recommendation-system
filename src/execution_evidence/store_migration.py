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
