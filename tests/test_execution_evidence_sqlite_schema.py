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
    "execution_evidence_import_receipts",
    "roadmap_registry",
    "projects",
    "project_execution_events",
}

EXPECTED_INDEXES = {
    "idx_repositories_workspace",
    "idx_evidence_repository_timeline",
    "idx_evidence_repository_type",
    "idx_attributions_repository_stage",
    "idx_attributions_evidence",
    "idx_attributions_public_identity",
    "idx_attributions_scoped_identity",
    "idx_attributions_legacy_identity",
    "idx_jobs_workspace_status",
    "idx_jobs_repository_status",
    "idx_import_receipts_source_hash",
    "idx_roadmap_registry_workspace_created",
    "idx_roadmap_registry_workspace_hash",
    "idx_projects_workspace_updated",
    "idx_roadmap_registry_public_snapshot",
    "idx_roadmap_registry_project_created",
    "idx_project_execution_events_actor",
    "idx_project_execution_events_timeline",
    "idx_project_execution_events_client_replay",
    "idx_project_execution_events_provider_replay",
    "idx_project_execution_events_supersedes",
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


def test_project_lifecycle_revision_defaults_to_zero(
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
                '2026-07-14T12:00:00Z',
                '2026-07-14T12:00:00Z'
            )
            """
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
            VALUES (
                'proj_revision',
                'local',
                'Revision project',
                'active',
                '2026-07-14T12:00:00Z',
                '2026-07-14T12:00:00Z'
            )
            """
        )

        revision = connection.execute(
            """
            SELECT revision
            FROM projects
            WHERE project_id = 'proj_revision'
            """
        ).fetchone()["revision"]

        assert revision == 0
    finally:
        connection.close()


def test_version_nine_project_upgrades_with_zero_revision(
    tmp_path: Path,
    monkeypatch,
):
    import execution_evidence.sqlite_schema as schema

    database_path = tmp_path / "solvyn.db"
    current_migrations = schema.MIGRATIONS

    monkeypatch.setattr(
        schema,
        "MIGRATIONS",
        tuple(
            migration
            for migration in current_migrations
            if migration.version <= 9
        ),
    )

    version = schema.initialize_execution_evidence_database(
        database_path
    )

    assert version == 9

    connection = (
        schema.connect_execution_evidence_database(
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
                '2026-07-14T12:00:00Z',
                '2026-07-14T12:00:00Z'
            )
            """
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
            VALUES (
                'proj_existing',
                'local',
                'Existing project',
                'archived',
                '2026-07-14T12:00:00Z',
                '2026-07-14T13:00:00Z'
            )
            """
        )
    finally:
        connection.close()

    monkeypatch.setattr(
        schema,
        "MIGRATIONS",
        current_migrations,
    )

    upgraded_version = (
        schema.initialize_execution_evidence_database(
            database_path
        )
    )

    connection = (
        schema.connect_execution_evidence_database(
            database_path
        )
    )

    try:
        project = connection.execute(
            """
            SELECT
                project_id,
                title,
                status,
                revision
            FROM projects
            WHERE project_id = 'proj_existing'
            """
        ).fetchone()
    finally:
        connection.close()

    assert upgraded_version == (
        schema.CURRENT_SQLITE_SCHEMA_VERSION
    )
    assert project is not None
    assert project["project_id"] == "proj_existing"
    assert project["title"] == "Existing project"
    assert project["status"] == "archived"
    assert project["revision"] == 0


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


def test_schema_allows_pending_attribution_without_decision_time(
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
                'local',
                'github:owner/repository',
                'github',
                'owner',
                'repository',
                'https://github.com/owner/repository',
                0,
                2,
                '2026-07-13T12:00:00Z',
                '2026-07-13T12:00:00Z',
                '2026-07-13T12:00:00Z'
            )
            """
        )

        repository_id = cursor.lastrowid

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                "github:owner/repository:commit:abc",
                "build-mvp",
                "deterministic",
                0.8,
                "Matched roadmap terminology.",
                "suggested",
                None,
                "{}",
                0,
            ),
        )

        row = connection.execute(
            """
            SELECT decided_at, status
            FROM evidence_attributions
            WHERE repository_id = ?
            """,
            (repository_id,),
        ).fetchone()

        assert row["decided_at"] is None
        assert row["status"] == "suggested"
    finally:
        connection.close()


def test_existing_attributions_survive_version_two_migration(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            (MIGRATIONS[0],),
        )
        apply_execution_evidence_migrations(
            connection
        )

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
                'local',
                'github:owner/repository',
                'github',
                'owner',
                'repository',
                'https://github.com/owner/repository',
                0,
                2,
                '2026-07-13T12:00:00Z',
                '2026-07-13T12:00:00Z',
                '2026-07-13T12:00:00Z'
            )
            """
        )

        repository_id = cursor.lastrowid

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                "github:owner/repository:commit:abc",
                "build-mvp",
                "manual",
                1.0,
                "",
                "accepted",
                "2026-07-13T12:00:00Z",
                "{}",
                0,
            ),
        )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(
            connection
        )

        row = connection.execute(
            """
            SELECT
                evidence_key,
                roadmap_node_id,
                status,
                decided_at
            FROM evidence_attributions
            """
        ).fetchone()

        assert row["evidence_key"] == (
            "github:owner/repository:commit:abc"
        )
        assert row["roadmap_node_id"] == "build-mvp"
        assert row["status"] == "accepted"
        assert row["decided_at"] == (
            "2026-07-13T12:00:00Z"
        )
    finally:
        connection.close()


def test_schema_persists_import_receipt(
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
                "receipt-1",
                "json",
                "repositories.json",
                "abc123",
                1,
                1,
                2,
                4,
                1,
                '{"verified":true}',
                "2026-07-13T12:00:00Z",
            ),
        )

        row = connection.execute(
            """
            SELECT
                source_root_hash,
                repository_count,
                deterministic_report_json
            FROM execution_evidence_import_receipts
            WHERE receipt_id = ?
            """,
            ("receipt-1",),
        ).fetchone()

        assert row is not None
        assert row["source_root_hash"] == "abc123"
        assert row["repository_count"] == 2
        assert (
            row["deterministic_report_json"]
            == '{"verified":true}'
        )
    finally:
        connection.close()


def _insert_workspace_and_repository(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    repository_key: str,
) -> int:
    connection.execute(
        """
        INSERT INTO workspaces (
            workspace_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?)
        """,
        (
            workspace_id,
            "2026-07-14T12:00:00Z",
            "2026-07-14T12:00:00Z",
        ),
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            repository_key,
            "github",
            "owner",
            "repository",
            "https://github.com/owner/repository",
            0,
            3,
            "2026-07-14T12:00:00Z",
            "2026-07-14T12:00:00Z",
            "2026-07-14T12:00:00Z",
        ),
    )

    return int(cursor.lastrowid)


def _insert_roadmap_registry_record(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    project_direction_id: str,
) -> int:
    project_table_exists = (
        connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = 'projects'
            """
        ).fetchone()
        is not None
    )

    if not project_table_exists:
        cursor = connection.execute(
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
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                workspace_id,
                project_direction_id,
                "response-direction",
                "Project direction",
                "a" * 64,
                "{}",
                "2026-07-14T12:00:00Z",
            ),
        )

        return int(cursor.lastrowid)

    project_id = (
        "proj_test_" + project_direction_id
    )
    roadmap_snapshot_id = (
        "snap_test_" + project_direction_id
    )

    project_cursor = connection.execute(
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
            "Project direction",
            "active",
            "2026-07-14T12:00:00Z",
            "2026-07-14T12:00:00Z",
        ),
    )
    project_row_id = int(
        project_cursor.lastrowid
    )

    cursor = connection.execute(
        """
        INSERT INTO roadmap_registry (
            workspace_id,
            project_row_id,
            roadmap_snapshot_id,
            project_direction_id,
            response_direction_id,
            title,
            roadmap_hash,
            snapshot_json,
            created_at,
            supersedes_id
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL
        )
        """,
        (
            workspace_id,
            project_row_id,
            roadmap_snapshot_id,
            project_direction_id,
            "response-direction",
            "Project direction",
            "a" * 64,
            "{}",
            "2026-07-14T12:00:00Z",
        ),
    )

    return int(cursor.lastrowid)


def test_version_five_preserves_existing_attributions_as_legacy(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:4],
        )
        apply_execution_evidence_migrations(connection)

        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                "github:owner/repository:commit:abc",
                "build-mvp",
                "manual",
                1.0,
                "",
                "accepted",
                "2026-07-14T12:00:00Z",
                "{}",
                0,
            ),
        )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(connection)

        row = connection.execute(
            """
            SELECT
                attribution_row_id,
                attribution_id,
                roadmap_registry_id,
                project_direction_id,
                evidence_key,
                roadmap_node_id
            FROM evidence_attributions
            """
        ).fetchone()

        assert row["attribution_row_id"] == 1
        assert row["attribution_id"] is None
        assert row["roadmap_registry_id"] is None
        assert row["project_direction_id"] is None
        assert row["evidence_key"] == (
            "github:owner/repository:commit:abc"
        )
        assert row["roadmap_node_id"] == "build-mvp"
    finally:
        connection.close()


def test_scoped_attribution_identity_allows_same_stage_across_projects(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )
        first_registry_id = (
            _insert_roadmap_registry_record(
                connection,
                workspace_id="local",
                project_direction_id="project-one",
            )
        )
        second_registry_id = (
            _insert_roadmap_registry_record(
                connection,
                workspace_id="local",
                project_direction_id="project-two",
            )
        )

        statement = """
            INSERT INTO evidence_attributions (
                attribution_id,
                repository_id,
                roadmap_registry_id,
                project_id,
                roadmap_snapshot_id,
                project_direction_id,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """

        shared_values = (
            repository_id,
            "github:owner/repository:commit:abc",
            "build-mvp",
            "manual",
            1.0,
            "",
            "accepted",
            "2026-07-14T12:00:00Z",
            "{}",
        )

        connection.execute(
            statement,
            (
                "attribution-one",
                shared_values[0],
                first_registry_id,
                "proj_test_project-one",
                "snap_test_project-one",
                "project-one",
                *shared_values[1:],
                0,
            ),
        )
        connection.execute(
            statement,
            (
                "attribution-two",
                shared_values[0],
                second_registry_id,
                "proj_test_project-two",
                "snap_test_project-two",
                "project-two",
                *shared_values[1:],
                1,
            ),
        )

        count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM evidence_attributions
            """
        ).fetchone()["count"]

        assert count == 2
    finally:
        connection.close()


def test_scoped_attribution_rejects_cross_workspace_roadmap(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="repository-workspace",
            repository_key="github:owner/repository",
        )

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                "roadmap-workspace",
                "2026-07-14T12:00:00Z",
                "2026-07-14T12:00:00Z",
            ),
        )

        roadmap_registry_id = (
            _insert_roadmap_registry_record(
                connection,
                workspace_id="roadmap-workspace",
                project_direction_id="foreign-project",
            )
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match=(
                "Attribution durable identity does not "
                "match trusted roadmap"
            ),
        ):
            connection.execute(
                """
                INSERT INTO evidence_attributions (
                    attribution_id,
                    repository_id,
                    roadmap_registry_id,
                    project_id,
                    roadmap_snapshot_id,
                    project_direction_id,
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
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    "attribution-one",
                    repository_id,
                    roadmap_registry_id,
                    "proj_test_foreign-project",
                    "snap_test_foreign-project",
                    "foreign-project",
                    "github:owner/repository:commit:abc",
                    "build-mvp",
                    "manual",
                    1.0,
                    "",
                    "accepted",
                    "2026-07-14T12:00:00Z",
                    "{}",
                    0,
                ),
            )
    finally:
        connection.close()


def test_version_six_backfills_projects_and_snapshot_ids(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:5],
        )
        apply_execution_evidence_migrations(connection)

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                "local",
                "2026-07-14T12:00:00Z",
                "2026-07-14T12:00:00Z",
            ),
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
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                "local",
                "direction-one",
                "response-one",
                "First project",
                "a" * 64,
                "{}",
                "2026-07-14T12:00:00Z",
            ),
        )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(connection)

        row = connection.execute(
            """
            SELECT
                project.project_id,
                project.workspace_id,
                project.title,
                roadmap.project_row_id,
                roadmap.roadmap_snapshot_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            """
        ).fetchone()

        assert row is not None
        assert row["project_id"] == (
            "proj_migrated_direction-one"
        )
        assert row["workspace_id"] == "local"
        assert row["title"] == "First project"
        assert row["project_row_id"] is not None
        assert row["roadmap_snapshot_id"] == (
            "snap_migrated_direction-one"
        )
    finally:
        connection.close()


def test_version_six_backfill_is_workspace_isolated(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:5],
        )
        apply_execution_evidence_migrations(connection)

        for workspace_id in (
            "workspace-one",
            "workspace-two",
        ):
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    workspace_id,
                    "2026-07-14T12:00:00Z",
                    "2026-07-14T12:00:00Z",
                ),
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
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    workspace_id,
                    "shared-direction",
                    "response-direction",
                    f"Project for {workspace_id}",
                    "a" * 64,
                    "{}",
                    "2026-07-14T12:00:00Z",
                ),
            )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(connection)

        rows = connection.execute(
            """
            SELECT
                project.workspace_id,
                project.project_id,
                roadmap.roadmap_snapshot_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            ORDER BY project.workspace_id
            """
        ).fetchall()

        assert [
            row["workspace_id"]
            for row in rows
        ] == [
            "workspace-one",
            "workspace-two",
        ]
        assert all(
            row["project_id"]
            == "proj_migrated_shared-direction"
            for row in rows
        )
        assert all(
            row["roadmap_snapshot_id"]
            == "snap_migrated_shared-direction"
            for row in rows
        )
    finally:
        connection.close()


def test_roadmap_project_scope_rejects_cross_workspace_link(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        for workspace_id in (
            "project-workspace",
            "roadmap-workspace",
        ):
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    workspace_id,
                    "2026-07-14T12:00:00Z",
                    "2026-07-14T12:00:00Z",
                ),
            )

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
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "project-one",
                "project-workspace",
                "Foreign project",
                "active",
                "2026-07-14T12:00:00Z",
                "2026-07-14T12:00:00Z",
            ),
        )
        project_row_id = int(cursor.lastrowid)

        with pytest.raises(
            sqlite3.IntegrityError,
            match=(
                "Roadmap project scope does not "
                "match workspace"
            ),
        ):
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
                    ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?
                )
                """,
                (
                    "roadmap-workspace",
                    "direction-one",
                    "response-one",
                    "Roadmap",
                    "a" * 64,
                    "{}",
                    "2026-07-14T12:00:00Z",
                    project_row_id,
                    "snapshot-one",
                ),
            )
    finally:
        connection.close()


def test_public_snapshot_id_is_unique_per_workspace(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                "local",
                "2026-07-14T12:00:00Z",
                "2026-07-14T12:00:00Z",
            ),
        )

        for direction_id in (
            "direction-one",
            "direction-two",
        ):
            if direction_id == "direction-two":
                expectation = pytest.raises(
                    sqlite3.IntegrityError
                )
            else:
                from contextlib import nullcontext
                expectation = nullcontext()

            with expectation:
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
                        roadmap_snapshot_id
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, NULL, ?
                    )
                    """,
                    (
                        "local",
                        direction_id,
                        f"response-{direction_id}",
                        "Project",
                        "a" * 64,
                        "{}",
                        "2026-07-14T12:00:00Z",
                        "shared-snapshot-id",
                    ),
                )
    finally:
        connection.close()


def test_version_seven_backfills_durable_attribution_identity(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:6],
        )
        apply_execution_evidence_migrations(connection)

        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )

        roadmap_registry_id = (
            _insert_roadmap_registry_record(
                connection,
                workspace_id="local",
                project_direction_id="direction-one",
            )
        )

        roadmap = connection.execute(
            """
            SELECT
                roadmap.project_row_id,
                roadmap.roadmap_snapshot_id,
                project.project_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE roadmap.roadmap_registry_id = ?
            """,
            (roadmap_registry_id,),
        ).fetchone()

        connection.execute(
            """
            INSERT INTO evidence_attributions (
                attribution_id,
                repository_id,
                roadmap_registry_id,
                project_direction_id,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "attribution-one",
                repository_id,
                roadmap_registry_id,
                "direction-one",
                "github:owner/repository:commit:abc",
                "build-mvp",
                "manual",
                1.0,
                "",
                "accepted",
                "2026-07-14T12:00:00Z",
                "{}",
                0,
            ),
        )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(connection)

        row = connection.execute(
            """
            SELECT
                project_id,
                roadmap_snapshot_id,
                project_direction_id
            FROM evidence_attributions
            """
        ).fetchone()

        assert row["project_id"] == roadmap["project_id"]
        assert (
            row["roadmap_snapshot_id"]
            == roadmap["roadmap_snapshot_id"]
        )
        assert (
            row["project_direction_id"]
            == "direction-one"
        )
    finally:
        connection.close()


def test_version_seven_keeps_legacy_attribution_unscoped(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                "github:owner/repository:commit:abc",
                "build-mvp",
                "manual",
                1.0,
                "",
                "accepted",
                "2026-07-14T12:00:00Z",
                "{}",
                0,
            ),
        )

        row = connection.execute(
            """
            SELECT
                attribution_id,
                roadmap_registry_id,
                project_id,
                roadmap_snapshot_id,
                project_direction_id
            FROM evidence_attributions
            """
        ).fetchone()

        assert all(
            row[column] is None
            for column in (
                "attribution_id",
                "roadmap_registry_id",
                "project_id",
                "roadmap_snapshot_id",
                "project_direction_id",
            )
        )
    finally:
        connection.close()


def test_version_seven_rejects_partial_attribution_identity(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="fully scoped or fully legacy",
        ):
            connection.execute(
                """
                INSERT INTO evidence_attributions (
                    attribution_id,
                    repository_id,
                    project_direction_id,
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "attribution-one",
                    repository_id,
                    "direction-one",
                    "github:owner/repository:commit:abc",
                    "build-mvp",
                    "manual",
                    1.0,
                    "",
                    "accepted",
                    "2026-07-14T12:00:00Z",
                    "{}",
                    0,
                ),
            )
    finally:
        connection.close()


def test_version_eight_uses_durable_attribution_indexes(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        rows = connection.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE
                type = 'index'
                AND name IN (
                    'idx_attributions_scoped_identity',
                    'idx_attributions_repository_stage',
                    'idx_attributions_evidence'
                )
            ORDER BY name
            """
        ).fetchall()

        statements = {
            row["name"]: " ".join(
                str(row["sql"]).split()
            )
            for row in rows
        }

        assert set(statements) == {
            "idx_attributions_scoped_identity",
            "idx_attributions_repository_stage",
            "idx_attributions_evidence",
        }

        scoped_sql = statements[
            "idx_attributions_scoped_identity"
        ]

        assert "project_id" in scoped_sql
        assert "roadmap_snapshot_id" in scoped_sql
        assert (
            "project_direction_id"
            not in scoped_sql
        )

        for name in (
            "idx_attributions_repository_stage",
            "idx_attributions_evidence",
        ):
            assert "project_id" in statements[name]
            assert (
                "roadmap_snapshot_id"
                in statements[name]
            )
            assert (
                "project_direction_id"
                not in statements[name]
            )
    finally:
        connection.close()


def test_version_eight_preserves_legacy_identity_index(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        row = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE
                type = 'index'
                AND name =
                    'idx_attributions_legacy_identity'
            """
        ).fetchone()

        assert row is not None
        sql = " ".join(str(row["sql"]).split())

        assert "project_direction_id IS NULL" in sql
        assert "project_id" not in sql
        assert "roadmap_snapshot_id" not in sql
    finally:
        connection.close()


def test_version_eight_rejects_durable_identity_collisions(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:7],
        )
        apply_execution_evidence_migrations(connection)

        repository_id = _insert_workspace_and_repository(
            connection,
            workspace_id="local",
            repository_key="github:owner/repository",
        )

        first_registry_id = (
            _insert_roadmap_registry_record(
                connection,
                workspace_id="local",
                project_direction_id="direction-one",
            )
        )

        roadmap = connection.execute(
            """
            SELECT
                project.project_id,
                roadmap.roadmap_snapshot_id
            FROM roadmap_registry AS roadmap
            JOIN projects AS project
                ON project.project_row_id =
                    roadmap.project_row_id
            WHERE roadmap.roadmap_registry_id = ?
            """,
            (first_registry_id,),
        ).fetchone()

        connection.execute(
            "DROP INDEX idx_attributions_scoped_identity"
        )

        statement = """
            INSERT INTO evidence_attributions (
                attribution_id,
                repository_id,
                roadmap_registry_id,
                project_id,
                roadmap_snapshot_id,
                project_direction_id,
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
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """

        for position, attribution_id in enumerate(
            ("attribution-one", "attribution-two")
        ):
            connection.execute(
                statement,
                (
                    attribution_id,
                    repository_id,
                    first_registry_id,
                    roadmap["project_id"],
                    roadmap["roadmap_snapshot_id"],
                    "direction-one",
                    "github:owner/repository:commit:abc",
                    "build-mvp",
                    "manual",
                    1.0,
                    "",
                    "accepted",
                    "2026-07-14T12:00:00Z",
                    "{}",
                    position,
                ),
            )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )

        with pytest.raises(SQLiteMigrationError):
            apply_execution_evidence_migrations(
                connection
            )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 7
        )
    finally:
        connection.close()


def test_execution_event_supersession_schema_is_present(
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
        columns = {
            str(row["name"])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    project_execution_events
                )
                """
            )
        }

        assert (
            "supersedes_execution_event_id"
            in columns
        )
        assert (
            "idx_project_execution_events_supersedes"
            in _database_objects(
                connection,
                "index",
            )
        )
    finally:
        connection.close()


def test_version_11_event_stream_upgrades_without_data_loss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = tmp_path / "solvyn.db"
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS[:11],
        )
        apply_execution_evidence_migrations(
            connection
        )

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?)
            """,
            (
                "local",
                "2026-07-22T12:00:00+00:00",
                "2026-07-22T12:00:00+00:00",
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
                "Test project",
                "active",
                "2026-07-22T12:00:00+00:00",
                "2026-07-22T12:00:00+00:00",
            ),
        )

        project = connection.execute(
            """
            SELECT project_row_id
            FROM projects
            WHERE
                workspace_id = 'local'
                AND project_id = 'proj_test'
            """
        ).fetchone()

        connection.execute(
            """
            INSERT INTO project_execution_events (
                execution_event_id,
                workspace_id,
                project_row_id,
                project_id,
                event_type,
                occurred_at,
                recorded_at,
                source_provider,
                provider_idempotency_key,
                ingestion_method,
                visibility,
                payload_json,
                event_fingerprint,
                created_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                "evt_existing",
                "local",
                int(project["project_row_id"]),
                "proj_test",
                "commit.created",
                "2026-07-22T12:00:00+00:00",
                "2026-07-22T12:01:00+00:00",
                "github",
                "existing-delivery",
                "webhook",
                "project",
                "{}",
                "existing-fingerprint",
                "2026-07-22T12:01:00+00:00",
            ),
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 11
        )

        monkeypatch.setattr(
            "execution_evidence.sqlite_schema.MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(
            connection
        )

        stored = connection.execute(
            """
            SELECT
                execution_event_id,
                supersedes_execution_event_id
            FROM project_execution_events
            WHERE execution_event_id = ?
            """,
            ("evt_existing",),
        ).fetchone()

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 12
        )
        assert stored is not None
        assert (
            stored["execution_event_id"]
            == "evt_existing"
        )
        assert (
            stored[
                "supersedes_execution_event_id"
            ]
            is None
        )
    finally:
        connection.close()
