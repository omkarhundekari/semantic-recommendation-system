import sqlite3
from pathlib import Path

import pytest

from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MIGRATIONS,
    SQLiteMigration,
    SQLiteMigrationError,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


EXPECTED_TABLES = {
    "execution_evidence_schema_migrations",
    "workspaces",
    "repositories",
    "evidence_items",
    "evidence_attributions",
    "repository_sync_states",
    "repository_sync_snapshots",
    "execution_jobs",
}

EXPECTED_INDEXES = {
    "idx_repositories_workspace",
    "idx_evidence_repository_timeline",
    "idx_evidence_repository_type",
    "idx_attributions_repository_stage",
    "idx_attributions_evidence",
    "idx_jobs_workspace_status",
    "idx_jobs_repository_status",
}


def _database_objects(
    connection: sqlite3.Connection,
    object_type: str,
) -> set:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = ?
        """,
        (object_type,),
    )

    return {
        str(row["name"])
        for row in rows
    }


def test_initialization_creates_versioned_schema(
    tmp_path: Path,
):
    database_path = (
        tmp_path
        / "execution-evidence"
        / "solvyn.db"
    )

    version = (
        initialize_execution_evidence_database(
            database_path
        )
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        assert version == (
            CURRENT_SQLITE_SCHEMA_VERSION
        )
        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == CURRENT_SQLITE_SCHEMA_VERSION
        )
        assert EXPECTED_TABLES.issubset(
            _database_objects(
                connection,
                "table",
            )
        )
        assert EXPECTED_INDEXES.issubset(
            _database_objects(
                connection,
                "index",
            )
        )
    finally:
        connection.close()


def test_initialization_is_idempotent(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    first_version = (
        initialize_execution_evidence_database(
            database_path
        )
    )
    second_version = (
        initialize_execution_evidence_database(
            database_path
        )
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        migration_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM execution_evidence_schema_migrations
            """
        ).fetchone()["count"]

        assert first_version == second_version
        assert migration_count == len(MIGRATIONS)
    finally:
        connection.close()


def test_connection_enables_required_pragmas(
    tmp_path: Path,
):
    connection = (
        connect_execution_evidence_database(
            tmp_path / "solvyn.db"
        )
    )

    try:
        foreign_keys = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0]
        busy_timeout = connection.execute(
            "PRAGMA busy_timeout"
        ).fetchone()[0]
        journal_mode = connection.execute(
            "PRAGMA journal_mode"
        ).fetchone()[0]
        synchronous = connection.execute(
            "PRAGMA synchronous"
        ).fetchone()[0]

        assert foreign_keys == 1
        assert busy_timeout == 5000
        assert journal_mode.lower() == "wal"
        assert synchronous == 1
    finally:
        connection.close()


def test_foreign_keys_prevent_orphaned_evidence(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError
        ):
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
                    payload_json,
                    position
                )
                VALUES (
                    999,
                    'github:owner/repo:commit:abc',
                    'commit',
                    'abc',
                    'Title',
                    '',
                    'https://github.com/owner/repo/commit/abc',
                    '2026-07-13T12:00:00Z',
                    '2026-07-13T12:00:00Z',
                    '2026-07-13T12:00:00Z',
                    '{}',
                    0
                )
                """
            )
    finally:
        connection.close()


def test_repository_identity_is_unique_within_workspace(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (
                'local',
                '2026-07-13T12:00:00Z',
                '2026-07-13T12:00:00Z'
            )
            """
        )

        values = (
            "local",
            "github:owner/repository",
            "github",
            "owner",
            "repository",
            "https://github.com/owner/repository",
            0,
            2,
            "2026-07-13T12:00:00Z",
            "2026-07-13T12:00:00Z",
            "2026-07-13T12:00:00Z",
        )

        statement = """
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        connection.execute(
            statement,
            values,
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                statement,
                values,
            )
    finally:
        connection.close()


def test_failed_migration_rolls_back_schema_changes(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    broken_migration = SQLiteMigration(
        version=1,
        name="broken",
        sql="""
        CREATE TABLE should_rollback (
            id INTEGER PRIMARY KEY
        );

        THIS IS NOT VALID SQL;
        """,
    )

    monkeypatch.setattr(
        "execution_evidence.sqlite_schema.MIGRATIONS",
        (broken_migration,),
    )

    try:
        with pytest.raises(
            SQLiteMigrationError,
            match="Could not migrate",
        ):
            apply_execution_evidence_migrations(
                connection
            )

        assert "should_rollback" not in (
            _database_objects(
                connection,
                "table",
            )
        )

        migration_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM execution_evidence_schema_migrations
            """
        ).fetchone()["count"]

        assert migration_count == 0
    finally:
        connection.close()


def test_migration_versions_are_contiguous():
    versions = [
        migration.version
        for migration in MIGRATIONS
    ]

    assert versions == list(
        range(
            1,
            CURRENT_SQLITE_SCHEMA_VERSION + 1,
        )
    )
