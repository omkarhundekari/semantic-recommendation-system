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
from execution_evidence.sqlite_workspace_membership_store import (
    SQLiteWorkspaceMembershipStore,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    create_workspace_membership_id,
)
from execution_evidence.workspace_membership_store import (
    WorkspaceMembershipTransitionError,
)


NOW = datetime(
    2026,
    8,
    7,
    12,
    0,
    tzinfo=timezone.utc,
)
LATER = NOW + timedelta(minutes=1)
WORKSPACE_ID = "workspace-status-actor-test"


def _insert_workspace(
    connection,
    *,
    workspace_id: str = WORKSPACE_ID,
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
    principal_id: str,
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


def _insert_version_20_membership(
    connection,
    *,
    membership_id: str,
    principal_id: str,
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
            ?, ?, ?, 'active', 0, NULL, ?, ?, ?
        )
        """,
        (
            membership_id,
            WORKSPACE_ID,
            principal_id,
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )


def _prepare_current_database(
    path: Path,
):
    initialize_execution_evidence_database(path)

    actor_id = create_principal_id()
    target_id = create_principal_id()

    connection = connect_execution_evidence_database(
        path
    )

    try:
        _insert_workspace(connection)
        _insert_principal(
            connection,
            actor_id,
        )
        _insert_principal(
            connection,
            target_id,
        )
    finally:
        connection.close()

    return actor_id, target_id


def test_status_actor_attribution_is_schema_version_21(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"

    version = initialize_execution_evidence_database(
        path
    )

    assert version == 22
    assert CURRENT_SQLITE_SCHEMA_VERSION == 22

    connection = connect_execution_evidence_database(
        path
    )

    try:
        columns = {
            str(row["name"])
            for row in connection.execute(
                """
                PRAGMA table_info(
                    workspace_membership_status_transitions
                )
                """
            )
        }

        assert "changed_by_principal_id" in columns

        foreign_keys = connection.execute(
            """
            PRAGMA foreign_key_list(
                workspace_membership_status_transitions
            )
            """
        ).fetchall()

        assert any(
            row["table"] == "principals"
            and row["from"]
            == "changed_by_principal_id"
            and row["to"] == "principal_id"
            for row in foreign_keys
        )
    finally:
        connection.close()


def test_version_20_history_upgrades_without_actor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    path = tmp_path / "solvyn.db"
    original_migrations = MIGRATIONS

    connection = connect_execution_evidence_database(
        path
    )

    principal_id = create_principal_id()
    membership_id = create_workspace_membership_id()

    try:
        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            original_migrations[:20],
        )

        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 20
        )

        _insert_workspace(connection)
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_version_20_membership(
            connection,
            membership_id=membership_id,
            principal_id=principal_id,
        )

        before = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM workspace_membership_status_transitions
            WHERE membership_id = ?
            """,
            (membership_id,),
        ).fetchone()["count"]

        assert before == 1

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            original_migrations,
        )

        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 22
        )

        row = connection.execute(
            """
            SELECT changed_by_principal_id
            FROM workspace_membership_status_transitions
            WHERE membership_id = ?
            """,
            (membership_id,),
        ).fetchone()

        assert row is not None
        assert row[
            "changed_by_principal_id"
        ] is None
    finally:
        connection.close()


def test_status_transition_persists_actor(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    actor_id, target_id = _prepare_current_database(
        path
    )

    membership = WorkspaceMembership(
        membership_id=create_workspace_membership_id(),
        workspace_id=WORKSPACE_ID,
        principal_id=target_id,
        status="active",
        role=None,
        revision=0,
        created_by_principal_id=actor_id,
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    stored = store.create(membership)

    result = store.transition_status(
        stored.membership_id,
        new_status="suspended",
        changed_at=LATER,
        expected_revision=0,
        reason="Administrative suspension",
        changed_by_principal_id=actor_id,
    )

    assert (
        result.transition.changed_by_principal_id
        == actor_id
    )

    history = store.list_transitions(
        stored.membership_id
    )

    assert len(history) == 2
    assert history[0].changed_by_principal_id is None
    assert (
        history[1].changed_by_principal_id
        == actor_id
    )


def test_status_transition_actor_must_exist(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    actor_id, target_id = _prepare_current_database(
        path
    )

    membership = WorkspaceMembership(
        membership_id=create_workspace_membership_id(),
        workspace_id=WORKSPACE_ID,
        principal_id=target_id,
        status="active",
        role=None,
        revision=0,
        created_by_principal_id=actor_id,
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )

    stored = store.create(membership)

    missing_actor_id = create_principal_id()

    with pytest.raises(
        WorkspaceMembershipTransitionError
    ):
        store.transition_status(
            stored.membership_id,
            new_status="suspended",
            changed_at=LATER,
            expected_revision=0,
            changed_by_principal_id=missing_actor_id,
        )

    current = store.load_by_id(
        stored.membership_id
    )

    assert current.status == "active"
    assert current.revision == 0


def test_status_transition_history_remains_immutable(
    tmp_path: Path,
):
    path = tmp_path / "solvyn.db"
    actor_id, target_id = _prepare_current_database(
        path
    )

    membership = WorkspaceMembership(
        membership_id=create_workspace_membership_id(),
        workspace_id=WORKSPACE_ID,
        principal_id=target_id,
        status="active",
        role=None,
        revision=0,
        created_by_principal_id=actor_id,
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )

    store = SQLiteWorkspaceMembershipStore(
        path,
        workspace_id=WORKSPACE_ID,
    )
    stored = store.create(membership)

    result = store.transition_status(
        stored.membership_id,
        new_status="suspended",
        changed_at=LATER,
        expected_revision=0,
        changed_by_principal_id=actor_id,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        with pytest.raises(Exception):
            connection.execute(
                """
                UPDATE workspace_membership_status_transitions
                SET changed_by_principal_id = NULL
                WHERE transition_id = ?
                """,
                (
                    result.transition.transition_id,
                ),
            )
    finally:
        connection.close()
