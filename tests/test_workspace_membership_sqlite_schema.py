from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

import execution_evidence.sqlite_schema as schema
from execution_evidence.principal import (
    create_principal_id,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MIGRATIONS,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    2,
    12,
    0,
    tzinfo=timezone.utc,
).isoformat()


def _insert_principal(
    connection,
    *,
    principal_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO principals (
            principal_id,
            principal_kind,
            status,
            created_at,
            updated_at
        )
        VALUES (?, 'human', 'active', ?, ?)
        """,
        (
            principal_id,
            NOW,
            NOW,
        ),
    )


def _insert_workspace(
    connection,
    workspace_id: str,
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


def _insert_active_membership(
    connection,
    *,
    membership_id: str,
    workspace_id: str,
    principal_id: str,
):
    return connection.execute(
        """
        INSERT INTO workspace_memberships (
            membership_id,
            workspace_id,
            principal_id,
            status,
            revision,
            created_at,
            updated_at,
            status_changed_at
        )
        VALUES (?, ?, ?, 'active', 0, ?, ?, ?)
        """,
        (
            membership_id,
            workspace_id,
            principal_id,
            NOW,
            NOW,
            NOW,
        ),
    )


def _transition_membership(
    connection,
    *,
    transition_id: str,
    membership_row_id: int,
    membership_id: str,
    workspace_id: str,
    principal_id: str,
    previous_status: str,
    new_status: str,
    previous_revision: int,
):
    connection.execute(
        """
        INSERT INTO workspace_membership_status_transitions (
            transition_id,
            membership_row_id,
            membership_id,
            workspace_id,
            principal_id,
            previous_status,
            new_status,
            previous_revision,
            resulting_revision,
            changed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            transition_id,
            membership_row_id,
            membership_id,
            workspace_id,
            principal_id,
            previous_status,
            new_status,
            previous_revision,
            previous_revision + 1,
            NOW,
        ),
    )


def test_membership_foundation_is_schema_version_16():
    migration = MIGRATIONS[15]

    assert migration.version == 16
    assert (
        migration.name
        == "create_workspace_membership_foundation"
    )


def test_fresh_schema_contains_membership_foundation(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    version = initialize_execution_evidence_database(
        database_path
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

        user_version = int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert version == CURRENT_SQLITE_SCHEMA_VERSION
    assert {
        "workspace_memberships",
        "workspace_membership_status_transitions",
    }.issubset(tables)

    assert (
        "idx_workspace_memberships_current"
        in indexes
    )
    assert (
        "idx_workspace_membership_transitions_history"
        in indexes
    )
    assert user_version == CURRENT_SQLITE_SCHEMA_VERSION


def test_membership_requires_existing_workspace_and_principal(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO workspace_memberships (
                    membership_id,
                    workspace_id,
                    principal_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    status_changed_at
                )
                VALUES (
                    'wsm_missing_workspace',
                    'missing',
                    ?,
                    'active',
                    0,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    principal_id,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_only_one_current_membership_per_pair(
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
        principal_id = create_principal_id()

        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        connection.execute(
            """
            INSERT INTO workspace_memberships (
                membership_id,
                workspace_id,
                principal_id,
                status,
                revision,
                created_at,
                updated_at,
                status_changed_at
            )
            VALUES (?, ?, ?, ?, 0, ?, ?, ?)
            """,
            (
                "wsm_first",
                "workspace-test",
                principal_id,
                "active",
                NOW,
                NOW,
                NOW,
            ),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO workspace_memberships (
                    membership_id,
                    workspace_id,
                    principal_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    status_changed_at
                )
                VALUES (?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    "wsm_second",
                    "workspace-test",
                    principal_id,
                    "suspended",
                    NOW,
                    NOW,
                    NOW,
                ),
            )
    finally:
        connection.close()



def test_removed_membership_allows_rejoin_period(
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
        principal_id = create_principal_id()

        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_old",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        _transition_membership(
            connection,
            transition_id="wmt_remove_old",
            membership_row_id=int(
                cursor.lastrowid
            ),
            membership_id="wsm_old",
            workspace_id="workspace-test",
            principal_id=principal_id,
            previous_status="active",
            new_status="removed",
            previous_revision=0,
        )

        _insert_active_membership(
            connection,
            membership_id="wsm_new",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        rows = list(
            connection.execute(
                """
                SELECT
                    membership_id,
                    status,
                    revision
                FROM workspace_memberships
                WHERE
                    workspace_id = ?
                    AND principal_id = ?
                ORDER BY membership_row_id
                """,
                (
                    "workspace-test",
                    principal_id,
                ),
            )
        )

        assert len(rows) == 2
        assert rows[0]["membership_id"] == (
            "wsm_old"
        )
        assert rows[0]["status"] == "removed"
        assert rows[0]["revision"] == 1

        assert rows[1]["membership_id"] == (
            "wsm_new"
        )
        assert rows[1]["status"] == "active"
        assert rows[1]["revision"] == 0
    finally:
        connection.close()


def test_removed_membership_is_terminal(
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
        principal_id = create_principal_id()

        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_removed",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        _transition_membership(
            connection,
            transition_id=(
                "wmt_remove_terminal"
            ),
            membership_row_id=int(
                cursor.lastrowid
            ),
            membership_id="wsm_removed",
            workspace_id="workspace-test",
            principal_id=principal_id,
            previous_status="active",
            new_status="removed",
            previous_revision=0,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal",
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    status = 'active',
                    revision = 2,
                    updated_at = ?,
                    status_changed_at = ?
                WHERE membership_id = ?
                """,
                (
                    NOW,
                    NOW,
                    "wsm_removed",
                ),
            )

        stored = connection.execute(
            """
            SELECT status, revision
            FROM workspace_memberships
            WHERE membership_id = ?
            """,
            ("wsm_removed",),
        ).fetchone()

        assert stored is not None
        assert stored["status"] == "removed"
        assert stored["revision"] == 1
    finally:
        connection.close()


def test_transition_rows_are_immutable(
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
        principal_id = create_principal_id()

        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_test",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        genesis = connection.execute(
            """
            SELECT transition_id
            FROM workspace_membership_status_transitions
            WHERE
                membership_row_id = ?
                AND resulting_revision = 0
            """,
            (
                int(cursor.lastrowid),
            ),
        ).fetchone()

        assert genesis is not None

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE workspace_membership_status_transitions
                SET changed_at = ?
                WHERE transition_id = ?
                """,
                (
                    "2026-08-03T12:00:00+00:00",
                    genesis["transition_id"],
                ),
            )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM workspace_membership_status_transitions
                WHERE transition_id = ?
                """,
                (
                    genesis["transition_id"],
                ),
            )
    finally:
        connection.close()

def test_transition_revision_edge_is_enforced(
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
        principal_id = create_principal_id()

        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = connection.execute(
            """
            INSERT INTO workspace_memberships (
                membership_id,
                workspace_id,
                principal_id,
                status,
                revision,
                created_at,
                updated_at,
                status_changed_at
            )
            VALUES (?, ?, ?, 'active', 0, ?, ?, ?)
            """,
            (
                "wsm_test",
                "workspace-test",
                principal_id,
                NOW,
                NOW,
                NOW,
            ),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO workspace_membership_status_transitions (
                    transition_id,
                    membership_row_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_status,
                    new_status,
                    previous_revision,
                    resulting_revision,
                    changed_at
                )
                VALUES (
                    'wmt_bad',
                    ?,
                    'wsm_test',
                    'workspace-test',
                    ?,
                    'active',
                    'suspended',
                    0,
                    2,
                    ?
                )
                """,
                (
                    int(cursor.lastrowid),
                    principal_id,
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_version_15_upgrades_to_membership_foundation(
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
            MIGRATIONS[:15],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 15
        )

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS[:16],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 16
        )

        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 16
    finally:
        connection.close()

def test_membership_insert_automatically_creates_genesis(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(database_path)
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_id = create_principal_id()
        _insert_workspace(connection, "workspace-test")
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_genesis",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        transition = connection.execute(
            """
            SELECT *
            FROM workspace_membership_status_transitions
            WHERE membership_row_id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()

        assert transition is not None
        assert transition["previous_status"] is None
        assert transition["new_status"] == "active"
        assert transition["previous_revision"] is None
        assert transition["resulting_revision"] == 0
        assert transition["changed_at"] == NOW
    finally:
        connection.close()


def test_membership_cannot_be_inserted_as_removed(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(database_path)
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_id = create_principal_id()
        _insert_workspace(connection, "workspace-test")
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="must begin active",
        ):
            connection.execute(
                """
                INSERT INTO workspace_memberships (
                    membership_id,
                    workspace_id,
                    principal_id,
                    status,
                    revision,
                    created_at,
                    updated_at,
                    status_changed_at
                )
                VALUES (?, ?, ?, 'removed', 1, ?, ?, ?)
                """,
                (
                    "wsm_invalid",
                    "workspace-test",
                    principal_id,
                    NOW,
                    NOW,
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_direct_membership_state_update_is_rejected(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(database_path)
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_id = create_principal_id()
        _insert_workspace(connection, "workspace-test")
        _insert_principal(
            connection,
            principal_id=principal_id,
        )
        _insert_active_membership(
            connection,
            membership_id="wsm_test",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="authoritative transition",
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    status = 'suspended',
                    revision = 1
                WHERE membership_id = 'wsm_test'
                """
            )
    finally:
        connection.close()


def test_transition_must_match_current_membership_state(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(database_path)
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_id = create_principal_id()
        _insert_workspace(connection, "workspace-test")
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_test",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="does not match current state",
        ):
            _transition_membership(
                connection,
                transition_id="wmt_bad_state",
                membership_row_id=int(
                    cursor.lastrowid
                ),
                membership_id="wsm_test",
                workspace_id="workspace-test",
                principal_id=principal_id,
                previous_status="suspended",
                new_status="active",
                previous_revision=0,
            )
    finally:
        connection.close()


def test_transition_atomically_advances_membership_cache(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(database_path)
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_id = create_principal_id()
        _insert_workspace(connection, "workspace-test")
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_test",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        _transition_membership(
            connection,
            transition_id="wmt_suspend",
            membership_row_id=int(cursor.lastrowid),
            membership_id="wsm_test",
            workspace_id="workspace-test",
            principal_id=principal_id,
            previous_status="active",
            new_status="suspended",
            previous_revision=0,
        )

        membership = connection.execute(
            """
            SELECT status, revision, status_changed_at
            FROM workspace_memberships
            WHERE membership_id = 'wsm_test'
            """
        ).fetchone()

        assert membership["status"] == "suspended"
        assert membership["revision"] == 1
        assert membership["status_changed_at"] == NOW
    finally:
        connection.close()

def test_removed_membership_explicitly_rejects_reactivation(
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
        principal_id = create_principal_id()
        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        cursor = _insert_active_membership(
            connection,
            membership_id="wsm_terminal_explicit",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        _transition_membership(
            connection,
            transition_id="wmt_terminal_explicit",
            membership_row_id=int(
                cursor.lastrowid
            ),
            membership_id="wsm_terminal_explicit",
            workspace_id="workspace-test",
            principal_id=principal_id,
            previous_status="active",
            new_status="removed",
            previous_revision=0,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal",
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    status = 'active',
                    revision = 2,
                    updated_at = ?,
                    status_changed_at = ?
                WHERE membership_id = ?
                """,
                (
                    NOW,
                    NOW,
                    "wsm_terminal_explicit",
                ),
            )
    finally:
        connection.close()


def test_membership_delete_is_blocked_without_foreign_keys(
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
        principal_id = create_principal_id()
        _insert_workspace(
            connection,
            "workspace-test",
        )
        _insert_principal(
            connection,
            principal_id=principal_id,
        )

        _insert_active_membership(
            connection,
            membership_id="wsm_delete_guard",
            workspace_id="workspace-test",
            principal_id=principal_id,
        )

        connection.execute(
            "PRAGMA foreign_keys = OFF"
        )

        assert (
            connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
            == 0
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM workspace_memberships
                WHERE membership_id = ?
                """,
                ("wsm_delete_guard",),
            )

        stored = connection.execute(
            """
            SELECT membership_id
            FROM workspace_memberships
            WHERE membership_id = ?
            """,
            ("wsm_delete_guard",),
        ).fetchone()

        assert stored is not None
    finally:
        connection.close()
