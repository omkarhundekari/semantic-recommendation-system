from __future__ import annotations

from pathlib import Path

import pytest

import execution_evidence.sqlite_schema as schema
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MIGRATIONS,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


def test_principal_foundation_is_schema_version_15():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 15
    assert MIGRATIONS[-1].version == 15
    assert (
        MIGRATIONS[-1].name
        == "create_principal_foundation"
    )


def test_fresh_schema_contains_principal_foundation(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

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
        tables = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        kinds = {
            str(row["principal_kind"])
            for row in connection.execute(
                """
                SELECT principal_kind
                FROM principal_kinds
                """
            )
        }

        user_version = int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert version == 15
    assert {
        "principal_kinds",
        "principals",
    }.issubset(tables)

    assert kinds == {
        "human",
        "service",
        "system",
        "agent",
    }
    assert user_version == 15


def test_version_14_upgrades_to_principal_foundation(
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
            schema,
            "MIGRATIONS",
            MIGRATIONS[:14],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 14
        )
        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 14

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(
            connection
        )

        kinds = {
            str(row["principal_kind"])
            for row in connection.execute(
                """
                SELECT principal_kind
                FROM principal_kinds
                """
            )
        }

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 15
        )
        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 15
        assert kinds == {
            "human",
            "service",
            "system",
            "agent",
        }
    finally:
        connection.close()


def test_version_14_data_survives_principal_migration(
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
            schema,
            "MIGRATIONS",
            MIGRATIONS[:14],
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
                "workspace-existing",
                "2026-08-01T12:00:00+00:00",
                "2026-08-01T12:00:00+00:00",
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
                "proj_existing_v14",
                "workspace-existing",
                "Existing project",
                "archived",
                "2026-08-01T12:00:00+00:00",
                "2026-08-01T12:01:00+00:00",
            ),
        )

        before = connection.execute(
            """
            SELECT
                project_id,
                workspace_id,
                title,
                status,
                revision,
                created_at,
                updated_at
            FROM projects
            WHERE project_id = ?
            """,
            ("proj_existing_v14",),
        ).fetchone()

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS,
        )
        apply_execution_evidence_migrations(
            connection
        )

        after = connection.execute(
            """
            SELECT
                project_id,
                workspace_id,
                title,
                status,
                revision,
                created_at,
                updated_at
            FROM projects
            WHERE project_id = ?
            """,
            ("proj_existing_v14",),
        ).fetchone()

        assert before is not None
        assert after is not None
        assert dict(after) == dict(before)

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 15
        )
    finally:
        connection.close()


def test_principal_migration_replay_is_idempotent(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    first = (
        initialize_execution_evidence_database(
            database_path
        )
    )
    second = (
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
        v15_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM execution_evidence_schema_migrations
            WHERE version = 15
            """
        ).fetchone()["count"]

        principal_count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM principals
            """
        ).fetchone()["count"]
    finally:
        connection.close()

    assert first == 15
    assert second == 15
    assert v15_count == 1
    assert principal_count == 0
