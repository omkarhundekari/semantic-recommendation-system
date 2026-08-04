from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
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
from execution_evidence.workspace_membership import (
    create_workspace_membership_id,
)


NOW = datetime(
    2026,
    8,
    4,
    12,
    0,
    tzinfo=timezone.utc,
)

LATER = NOW + timedelta(minutes=1)


def _insert_workspace(
    connection,
    workspace_id="workspace-role-test",
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
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_principal(
    connection,
    principal_id,
):
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
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _insert_membership(
    connection,
    *,
    membership_id,
    principal_id,
    workspace_id="workspace-role-test",
):
    connection.execute(
        """
        INSERT INTO workspace_memberships (
            membership_id,
            workspace_id,
            principal_id,
            status,
            revision,
            created_by_principal_id,
            created_at,
            updated_at,
            status_changed_at
        )
        VALUES (
            ?,
            ?,
            ?,
            'active',
            0,
            NULL,
            ?,
            ?,
            ?
        )
        """,
        (
            membership_id,
            workspace_id,
            principal_id,
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _membership_row(
    connection,
    membership_id,
):
    return connection.execute(
        """
        SELECT
            membership_row_id,
            membership_id,
            workspace_id,
            principal_id,
            status,
            role,
            revision,
            created_at,
            updated_at,
            status_changed_at
        FROM workspace_memberships
        WHERE membership_id = ?
        """,
        (membership_id,),
    ).fetchone()


def _create_current_membership(
    connection,
):
    principal_id = create_principal_id()
    membership_id = (
        create_workspace_membership_id()
    )

    _insert_workspace(connection)
    _insert_principal(
        connection,
        principal_id,
    )
    _insert_membership(
        connection,
        membership_id=membership_id,
        principal_id=principal_id,
    )

    return (
        principal_id,
        membership_id,
        _membership_row(
            connection,
            membership_id,
        ),
    )


def _assign_role(
    connection,
    *,
    row,
    new_role="owner",
    resulting_revision=1,
):
    connection.execute(
        """
        INSERT INTO workspace_membership_role_transitions (
            role_transition_id,
            membership_row_id,
            membership_id,
            workspace_id,
            principal_id,
            previous_role,
            new_role,
            previous_revision,
            resulting_revision,
            changed_at,
            changed_by_principal_id,
            reason
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            NULL,
            ?,
            0,
            ?,
            ?,
            NULL,
            'trusted bootstrap'
        )
        """,
        (
            "wmr_role_test",
            int(row["membership_row_id"]),
            row["membership_id"],
            row["workspace_id"],
            row["principal_id"],
            new_role,
            resulting_revision,
            LATER.isoformat(),
        ),
    )


def test_role_foundation_is_schema_version_20(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"

    version = (
        initialize_execution_evidence_database(
            path
        )
    )

    assert version == 20
    assert CURRENT_SQLITE_SCHEMA_VERSION == 20


def test_fresh_schema_contains_role_foundation(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        columns = {
            str(row["name"])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    workspace_memberships
                )
                """
            )
        }

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
        }

        assert "role" in columns
        assert (
            "workspace_membership_role_transitions"
            in tables
        )
        assert (
            "idx_workspace_membership_role_history"
            in indexes
        )
    finally:
        connection.close()


def test_version_19_membership_upgrades_unassigned(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "solvyn.db"
    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    original_migrations = MIGRATIONS

    try:
        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            original_migrations[:19],
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

        principal_id = create_principal_id()
        membership_id = (
            create_workspace_membership_id()
        )

        _insert_workspace(connection)
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_membership(
            connection,
            membership_id=membership_id,
            principal_id=principal_id,
        )

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            original_migrations,
        )

        apply_execution_evidence_migrations(
            connection
        )

        row = _membership_row(
            connection,
            membership_id,
        )

        role_history_count = (
            connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM workspace_membership_role_transitions
                WHERE membership_id = ?
                """,
                (membership_id,),
            ).fetchone()["count"]
        )

        assert row is not None
        assert row["role"] is None
        assert row["revision"] == 0
        assert role_history_count == 0

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 20
        )

        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 20
    finally:
        connection.close()


def test_new_membership_begins_unassigned_at_revision_zero(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            row,
        ) = _create_current_membership(
            connection
        )

        genesis = connection.execute(
            """
            SELECT
                previous_status,
                new_status,
                previous_revision,
                resulting_revision
            FROM workspace_membership_status_transitions
            WHERE membership_id = ?
            """,
            (membership_id,),
        ).fetchone()

        assert row["status"] == "active"
        assert row["role"] is None
        assert row["revision"] == 0

        assert genesis is not None
        assert genesis["previous_status"] is None
        assert genesis["new_status"] == "active"
        assert genesis["previous_revision"] is None
        assert genesis["resulting_revision"] == 0
    finally:
        connection.close()


def test_membership_cannot_be_created_with_assigned_role(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        principal_id = create_principal_id()

        _insert_workspace(connection)
        _insert_principal(
            connection,
            principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="must begin active, unassigned",
        ):
            connection.execute(
                """
                INSERT INTO workspace_memberships (
                    membership_id,
                    workspace_id,
                    principal_id,
                    status,
                    role,
                    revision,
                    created_by_principal_id,
                    created_at,
                    updated_at,
                    status_changed_at
                )
                VALUES (
                    ?,
                    'workspace-role-test',
                    ?,
                    'active',
                    'owner',
                    0,
                    NULL,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    create_workspace_membership_id(),
                    principal_id,
                    NOW.isoformat(),
                    NOW.isoformat(),
                    NOW.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_first_role_assignment_consumes_revision_one(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            row,
        ) = _create_current_membership(
            connection
        )

        original_status_changed_at = (
            row["status_changed_at"]
        )

        _assign_role(
            connection,
            row=row,
        )

        stored = _membership_row(
            connection,
            membership_id,
        )

        transition = connection.execute(
            """
            SELECT
                previous_role,
                new_role,
                previous_revision,
                resulting_revision,
                changed_by_principal_id
            FROM workspace_membership_role_transitions
            WHERE membership_id = ?
            """,
            (membership_id,),
        ).fetchone()

        assert stored["status"] == "active"
        assert stored["role"] == "owner"
        assert stored["revision"] == 1
        assert stored["updated_at"] == (
            LATER.isoformat()
        )
        assert (
            stored["status_changed_at"]
            == original_status_changed_at
        )

        assert transition["previous_role"] is None
        assert transition["new_role"] == "owner"
        assert transition["previous_revision"] == 0
        assert transition["resulting_revision"] == 1
        assert (
            transition["changed_by_principal_id"]
            is None
        )
    finally:
        connection.close()


def test_role_transition_requires_concrete_new_role(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            _,
            row,
        ) = _create_current_membership(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO workspace_membership_role_transitions (
                    role_transition_id,
                    membership_row_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_role,
                    new_role,
                    previous_revision,
                    resulting_revision,
                    changed_at,
                    changed_by_principal_id,
                    reason
                )
                VALUES (
                    'wmr_null_role',
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    NULL,
                    0,
                    1,
                    ?,
                    NULL,
                    NULL
                )
                """,
                (
                    int(row["membership_row_id"]),
                    row["membership_id"],
                    row["workspace_id"],
                    row["principal_id"],
                    LATER.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_direct_role_update_without_ledger_is_rejected(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            _,
        ) = _create_current_membership(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="role changes require an authoritative transition",
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    role = 'owner',
                    revision = 1,
                    updated_at = ?
                WHERE membership_id = ?
                """,
                (
                    LATER.isoformat(),
                    membership_id,
                ),
            )

        stored = _membership_row(
            connection,
            membership_id,
        )

        assert stored["role"] is None
        assert stored["revision"] == 0
    finally:
        connection.close()


def test_revision_only_touch_is_explicitly_rejected(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            _,
        ) = _create_current_membership(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match=(
                "revision changes require a status "
                "or role transition"
            ),
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    revision = 1,
                    updated_at = ?
                WHERE membership_id = ?
                """,
                (
                    LATER.isoformat(),
                    membership_id,
                ),
            )
    finally:
        connection.close()


def test_mixed_status_and_role_update_is_rejected(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            _,
        ) = _create_current_membership(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="status and role cannot change",
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET
                    status = 'suspended',
                    role = 'owner',
                    revision = 1,
                    updated_at = ?,
                    status_changed_at = ?
                WHERE membership_id = ?
                """,
                (
                    LATER.isoformat(),
                    LATER.isoformat(),
                    membership_id,
                ),
            )
    finally:
        connection.close()


def test_status_transition_after_role_assignment_uses_shared_clock(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            membership_id,
            row,
        ) = _create_current_membership(
            connection
        )

        _assign_role(
            connection,
            row=row,
        )

        changed_at = (
            LATER + timedelta(minutes=1)
        ).isoformat()

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
                changed_at,
                reason
            )
            VALUES (
                'wmt_after_role',
                ?,
                ?,
                ?,
                ?,
                'active',
                'suspended',
                1,
                2,
                ?,
                'test shared clock'
            )
            """,
            (
                int(row["membership_row_id"]),
                row["membership_id"],
                row["workspace_id"],
                row["principal_id"],
                changed_at,
            ),
        )

        stored = _membership_row(
            connection,
            membership_id,
        )

        assert stored["status"] == "suspended"
        assert stored["role"] == "owner"
        assert stored["revision"] == 2
    finally:
        connection.close()


def test_role_and_status_ledgers_cannot_reuse_revision(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            _,
            row,
        ) = _create_current_membership(
            connection
        )

        _assign_role(
            connection,
            row=row,
        )

        with pytest.raises(
            sqlite3.IntegrityError
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
                    changed_at,
                    reason
                )
                VALUES (
                    'wmt_collision',
                    ?,
                    ?,
                    ?,
                    ?,
                    'active',
                    'suspended',
                    0,
                    1,
                    ?,
                    NULL
                )
                """,
                (
                    int(row["membership_row_id"]),
                    row["membership_id"],
                    row["workspace_id"],
                    row["principal_id"],
                    LATER.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_role_transition_rows_are_immutable(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            _,
            row,
        ) = _create_current_membership(
            connection
        )

        _assign_role(
            connection,
            row=row,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE workspace_membership_role_transitions
                SET reason = 'rewritten'
                WHERE role_transition_id = 'wmr_role_test'
                """
            )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM workspace_membership_role_transitions
                WHERE role_transition_id = 'wmr_role_test'
                """
            )
    finally:
        connection.close()


def test_role_transition_requires_current_revision(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        (
            _,
            _,
            row,
        ) = _create_current_membership(
            connection
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="does not match current state",
        ):
            connection.execute(
                """
                INSERT INTO workspace_membership_role_transitions (
                    role_transition_id,
                    membership_row_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_role,
                    new_role,
                    previous_revision,
                    resulting_revision,
                    changed_at,
                    changed_by_principal_id,
                    reason
                )
                VALUES (
                    'wmr_stale',
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    'owner',
                    1,
                    2,
                    ?,
                    NULL,
                    NULL
                )
                """,
                (
                    int(row["membership_row_id"]),
                    row["membership_id"],
                    row["workspace_id"],
                    row["principal_id"],
                    LATER.isoformat(),
                ),
            )
    finally:
        connection.close()
