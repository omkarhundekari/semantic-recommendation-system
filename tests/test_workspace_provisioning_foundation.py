from datetime import datetime, timezone
import sqlite3
from uuid import uuid1

import pytest
from pydantic import ValidationError

import execution_evidence.sqlite_schema as schema
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
)
from execution_evidence.workspace import (
    ProvisionedWorkspace,
    create_workspace_id,
)


NOW = datetime(
    2026,
    8,
    9,
    12,
    0,
    tzinfo=timezone.utc,
)


def test_schema_version_is_23():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 26


def test_fresh_database_has_workspace_kind(
    tmp_path,
):
    path = tmp_path / "fresh.db"

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )

        columns = {
            row["name"]: row
            for row in connection.execute(
                "PRAGMA table_info(workspaces)"
            )
        }

        assert "workspace_kind" in columns
        assert (
            columns["workspace_kind"]["notnull"]
            == 1
        )
        assert (
            columns["workspace_kind"]["dflt_value"]
            == "'internal'"
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 26
        )
    finally:
        connection.close()


def test_workspace_insert_defaults_to_internal(
    tmp_path,
):
    path = tmp_path / "default-kind.db"

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
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
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

        row = connection.execute(
            """
            SELECT
                workspace_id,
                workspace_kind
            FROM workspaces
            WHERE workspace_id = ?
            """,
            ("local",),
        ).fetchone()

        assert row["workspace_id"] == "local"
        assert (
            row["workspace_kind"]
            == "internal"
        )
    finally:
        connection.close()


def test_workspace_kind_rejects_invalid_value(
    tmp_path,
):
    path = tmp_path / "invalid-kind.db"

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    created_at,
                    updated_at,
                    workspace_kind
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    "invalid-workspace",
                    NOW.isoformat(),
                    NOW.isoformat(),
                    "unknown",
                ),
            )
    finally:
        connection.close()


def test_v21_workspace_upgrades_as_internal(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "upgrade.db"

    all_migrations = schema.MIGRATIONS

    migrations_through_21 = tuple(
        migration
        for migration in all_migrations
        if migration.version <= 21
    )

    monkeypatch.setattr(
        schema,
        "MIGRATIONS",
        migrations_through_21,
    )

    connection = (
        connect_execution_evidence_database(path)
    )

    created_at = (
        "2026-08-01T12:00:00+00:00"
    )
    updated_at = (
        "2026-08-02T12:00:00+00:00"
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 21
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
                created_at,
                updated_at,
            ),
        )
    finally:
        connection.close()

    monkeypatch.setattr(
        schema,
        "MIGRATIONS",
        all_migrations,
    )

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )

        row = connection.execute(
            """
            SELECT
                workspace_id,
                created_at,
                updated_at,
                workspace_kind
            FROM workspaces
            WHERE workspace_id = ?
            """,
            ("local",),
        ).fetchone()

        assert row is not None
        assert row["workspace_id"] == "local"
        assert row["created_at"] == created_at
        assert row["updated_at"] == updated_at
        assert (
            row["workspace_kind"]
            == "internal"
        )

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert violations == []

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 26
        )
    finally:
        connection.close()


def test_workspace_kind_accepts_provisioned(
    tmp_path,
):
    path = tmp_path / "provisioned-kind.db"

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        apply_execution_evidence_migrations(
            connection
        )

        workspace_id = create_workspace_id()

        connection.execute(
            """
            INSERT INTO workspaces (
                workspace_id,
                created_at,
                updated_at,
                workspace_kind
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
                "provisioned",
            ),
        )

        row = connection.execute(
            """
            SELECT workspace_kind
            FROM workspaces
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        assert (
            row["workspace_kind"]
            == "provisioned"
        )
    finally:
        connection.close()


def test_create_workspace_id_is_canonical_uuid4():
    workspace_id = create_workspace_id()

    workspace = ProvisionedWorkspace(
        workspace_id=workspace_id,
        created_at=NOW,
        updated_at=NOW,
    )

    assert workspace.workspace_id == workspace_id
    assert workspace.workspace_kind == "provisioned"


@pytest.mark.parametrize(
    "workspace_id",
    [
        "local",
        "workspace-one",
        "wsp_not-a-uuid",
        "wsp_",
    ],
)
def test_provisioned_workspace_rejects_invalid_id(
    workspace_id,
):
    with pytest.raises(ValidationError):
        ProvisionedWorkspace(
            workspace_id=workspace_id,
            created_at=NOW,
            updated_at=NOW,
        )


def test_provisioned_workspace_rejects_non_v4_uuid():
    workspace_id = f"wsp_{uuid1()}"

    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        ProvisionedWorkspace(
            workspace_id=workspace_id,
            created_at=NOW,
            updated_at=NOW,
        )


def test_provisioned_workspace_rejects_naive_timestamp():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        ProvisionedWorkspace(
            workspace_id=create_workspace_id(),
            created_at=datetime(
                2026,
                8,
                9,
                12,
                0,
            ),
            updated_at=NOW,
        )
