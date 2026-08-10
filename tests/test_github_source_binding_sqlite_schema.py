from __future__ import annotations

import sqlite3
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


NOW = "2026-08-03T12:00:00+00:00"


def _seed_workspace_and_project(
    connection,
    *,
    workspace_id: str = "workspace-a",
    project_id: str = "project-a",
) -> None:
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
            NOW,
            NOW,
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
            "active",
            NOW,
            NOW,
        ),
    )


def test_github_source_binding_foundation_is_schema_version_19():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 25

    migration = next(
        migration
        for migration in MIGRATIONS
        if migration.version == 19
    )

    assert migration.name == (
        "create_github_source_binding_foundation"
    )


def test_fresh_schema_contains_github_source_binding_foundation(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    version = initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
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

        indexes = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            )
            if row["name"] is not None
        }

        triggers = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
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

    assert version == 25
    assert user_version == 25

    assert "github_source_bindings" in tables
    assert "github_webhook_credentials" in tables
    assert (
        "github_webhook_credential_authorities"
        in tables
    )

    assert (
        "idx_github_source_bindings_current_repository"
        in indexes
    )
    assert (
        "idx_github_webhook_authorities_current_pair"
        in indexes
    )

    expected_triggers = {
        "require_github_source_binding_genesis",
        "prevent_github_source_binding_update",
        "prevent_github_source_binding_delete",
        "require_github_webhook_credential_genesis",
        "prevent_github_webhook_credential_update",
        "prevent_github_webhook_credential_delete",
        "require_github_webhook_authority_genesis",
        "prevent_github_webhook_authority_update",
        "prevent_github_webhook_authority_delete",
    }

    assert expected_triggers <= triggers


def test_version_18_upgrades_to_github_binding_foundation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = tmp_path / "solvyn.db"

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS[:18],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 18
        )

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS[:19],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 19
        )

        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 19
    finally:
        connection.close()


def test_current_repository_binding_is_unique(
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
        _seed_workspace_and_project(connection)

        connection.execute(
            """
            INSERT INTO github_source_bindings (
                github_source_binding_id,
                repository_id,
                workspace_id,
                project_id,
                installation_id,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL)
            """,
            (
                "gsb_first",
                "1001",
                "workspace-a",
                "project-a",
                NOW,
            ),
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO github_source_bindings (
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL)
                """,
                (
                    "gsb_second",
                    "1001",
                    "workspace-a",
                    "project-a",
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_binding_requires_project_in_same_workspace(
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
        _seed_workspace_and_project(
            connection,
            workspace_id="workspace-a",
            project_id="project-a",
        )
        _seed_workspace_and_project(
            connection,
            workspace_id="workspace-b",
            project_id="project-b",
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO github_source_bindings (
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, NULL, ?, NULL, NULL)
                """,
                (
                    "gsb_cross",
                    "1002",
                    "workspace-a",
                    "project-b",
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_binding_retirement_is_unreachable_at_genesis(
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
        _seed_workspace_and_project(connection)

        with pytest.raises(
            sqlite3.IntegrityError,
            match="must begin current",
        ):
            connection.execute(
                """
                INSERT INTO github_source_bindings (
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    "gsb_retired",
                    "1001",
                    "workspace-a",
                    "project-a",
                    NOW,
                    NOW,
                    "bad registration",
                ),
            )
    finally:
        connection.close()


@pytest.mark.parametrize(
    "table_name",
    [
        "github_source_bindings",
        "github_webhook_credentials",
        "github_webhook_credential_authorities",
    ],
)
def test_github_binding_foundation_rows_cannot_be_deleted(
    tmp_path: Path,
    table_name: str,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        _seed_workspace_and_project(connection)

        connection.execute(
            """
            INSERT INTO github_source_bindings (
                github_source_binding_id,
                repository_id,
                workspace_id,
                project_id,
                installation_id,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (
                'gsb_test',
                '1001',
                'workspace-a',
                'project-a',
                NULL,
                ?,
                NULL,
                NULL
            )
            """,
            (NOW,),
        )

        connection.execute(
            """
            INSERT INTO github_webhook_credentials (
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (
                'gwc_test',
                'endpoint-test',
                NULL,
                'opaque-secret-reference',
                ?,
                NULL,
                NULL
            )
            """,
            (NOW,),
        )

        connection.execute(
            """
            INSERT INTO github_webhook_credential_authorities (
                github_webhook_credential_authority_id,
                github_webhook_credential_id,
                repository_id,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (
                'gwca_test',
                'gwc_test',
                '1001',
                ?,
                NULL,
                NULL
            )
            """,
            (NOW,),
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                f"DELETE FROM {table_name}"
            )
    finally:
        connection.close()


def test_one_credential_can_authorize_many_repositories(
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
            INSERT INTO github_webhook_credentials (
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                "gwc_test",
                "endpoint-test",
                "installation-1",
                "opaque-ref",
                NOW,
            ),
        )

        for authority_id, repository_id in (
            ("gwca_1", "1001"),
            ("gwca_2", "1002"),
        ):
            connection.execute(
                """
                INSERT INTO github_webhook_credential_authorities (
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, NULL, NULL)
                """,
                (
                    authority_id,
                    "gwc_test",
                    repository_id,
                    NOW,
                ),
            )

        count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM github_webhook_credential_authorities
                WHERE github_webhook_credential_id = ?
                """,
                ("gwc_test",),
            ).fetchone()[0]
        )

        assert count == 2
    finally:
        connection.close()


def test_two_credentials_can_authorize_same_repository(
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
        for credential_id, endpoint_id in (
            ("gwc_old", "endpoint-old"),
            ("gwc_new", "endpoint-new"),
        ):
            connection.execute(
                """
                INSERT INTO github_webhook_credentials (
                    github_webhook_credential_id,
                    webhook_endpoint_id,
                    installation_id,
                    secret_ref,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, NULL, ?, ?, NULL, NULL)
                """,
                (
                    credential_id,
                    endpoint_id,
                    f"secret-ref-{credential_id}",
                    NOW,
                ),
            )

        for authority_id, credential_id in (
            ("gwca_old", "gwc_old"),
            ("gwca_new", "gwc_new"),
        ):
            connection.execute(
                """
                INSERT INTO github_webhook_credential_authorities (
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, '1001', ?, NULL, NULL)
                """,
                (
                    authority_id,
                    credential_id,
                    NOW,
                ),
            )

        count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM github_webhook_credential_authorities
                WHERE repository_id = '1001'
                """
            ).fetchone()[0]
        )

        assert count == 2
    finally:
        connection.close()


def test_duplicate_current_credential_authority_is_rejected(
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
            INSERT INTO github_webhook_credentials (
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (
                'gwc_test',
                'endpoint-test',
                NULL,
                'opaque-ref',
                ?,
                NULL,
                NULL
            )
            """,
            (NOW,),
        )

        connection.execute(
            """
            INSERT INTO github_webhook_credential_authorities (
                github_webhook_credential_authority_id,
                github_webhook_credential_id,
                repository_id,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (
                'gwca_first',
                'gwc_test',
                '1001',
                ?,
                NULL,
                NULL
            )
            """,
            (NOW,),
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO github_webhook_credential_authorities (
                    github_webhook_credential_authority_id,
                    github_webhook_credential_id,
                    repository_id,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (
                    'gwca_second',
                    'gwc_test',
                    '1001',
                    ?,
                    NULL,
                    NULL
                )
                """,
                (NOW,),
            )
    finally:
        connection.close()


def test_secret_ref_is_opaque_nonempty_text_only(
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
        unusual_ref = (
            "provider://anything::future-format"
        )

        connection.execute(
            """
            INSERT INTO github_webhook_credentials (
                github_webhook_credential_id,
                webhook_endpoint_id,
                installation_id,
                secret_ref,
                created_at,
                retired_at,
                retired_reason
            )
            VALUES (?, ?, NULL, ?, ?, NULL, NULL)
            """,
            (
                "gwc_test",
                "endpoint-test",
                unusual_ref,
                NOW,
            ),
        )

        stored = connection.execute(
            """
            SELECT secret_ref
            FROM github_webhook_credentials
            WHERE github_webhook_credential_id = ?
            """,
            ("gwc_test",),
        ).fetchone()

        assert stored["secret_ref"] == unusual_ref
    finally:
        connection.close()
