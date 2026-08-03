from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest

from execution_evidence.principal import (
    Principal,
    create_principal_id,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
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
    WorkspaceMembershipAlreadyExistsError,
    WorkspaceMembershipInactiveError,
    WorkspaceMembershipNotFoundError,
    WorkspaceMembershipRevisionConflictError,
    WorkspaceMembershipStoreError,
    WorkspaceMembershipTransitionError,
    WorkspaceNotFoundError,
)


NOW = datetime(
    2026,
    8,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)


def _insert_workspace(
    database_path: Path,
    workspace_id: str,
) -> None:
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
            VALUES (?, ?, ?)
            """,
            (
                workspace_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _create_principal(
    database_path: Path,
) -> str:
    principal_id = create_principal_id()

    SQLitePrincipalStore(
        database_path
    ).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    return principal_id


def _membership(
    *,
    workspace_id: str,
    principal_id: str,
    membership_id: str = None,
    created_by_principal_id: str = None,
) -> WorkspaceMembership:
    return WorkspaceMembership(
        membership_id=(
            membership_id
            or create_workspace_membership_id()
        ),
        workspace_id=workspace_id,
        principal_id=principal_id,
        status="active",
        revision=0,
        created_by_principal_id=(
            created_by_principal_id
        ),
        created_at=NOW,
        updated_at=NOW,
        status_changed_at=NOW,
    )


def _setup(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    _insert_workspace(
        database_path,
        "workspace-one",
    )
    _insert_workspace(
        database_path,
        "workspace-two",
    )

    principal_id = _create_principal(
        database_path
    )

    return database_path, principal_id


def test_store_requires_exact_workspace_id(
    tmp_path: Path,
):
    with pytest.raises(
        ValueError,
        match="surrounding whitespace",
    ):
        SQLiteWorkspaceMembershipStore(
            tmp_path / "solvyn.db",
            workspace_id=" workspace-one",
        )


def test_create_and_load_membership(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = _membership(
        workspace_id="workspace-one",
        principal_id=principal_id,
    )

    created = store.create(membership)
    loaded = store.load_by_id(
        membership.membership_id
    )
    current = store.load_current(
        principal_id
    )

    assert created == membership
    assert loaded == membership
    assert current == membership


def test_creation_has_genesis_transition(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    transitions = store.list_transitions(
        membership.membership_id
    )

    assert len(transitions) == 1

    genesis = transitions[0]

    assert genesis.previous_status is None
    assert genesis.new_status == "active"
    assert genesis.previous_revision is None
    assert genesis.resulting_revision == 0
    assert genesis.changed_at == NOW


def test_create_requires_existing_workspace(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    principal_id = _create_principal(
        database_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="missing-workspace",
    )

    with pytest.raises(
        WorkspaceNotFoundError,
        match="does not exist",
    ):
        store.create(
            _membership(
                workspace_id="missing-workspace",
                principal_id=principal_id,
            )
        )


def test_duplicate_current_membership_rejected(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    with pytest.raises(
        WorkspaceMembershipAlreadyExistsError,
        match="already exists",
    ):
        store.create(
            _membership(
                workspace_id="workspace-one",
                principal_id=principal_id,
            )
        )


def test_duplicate_constraint_maps_to_domain_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    original_connect = (
        connect_execution_evidence_database
    )

    class ConnectionProxy:
        def __init__(self, connection):
            self._connection = connection
            self._hide_current_lookup = True

        def execute(self, sql, parameters=()):
            if (
                self._hide_current_lookup
                and "SELECT membership_id" in sql
                and "status != 'removed'" in sql
            ):
                self._hide_current_lookup = False

                class EmptyCursor:
                    @staticmethod
                    def fetchone():
                        return None

                return EmptyCursor()

            return self._connection.execute(
                sql,
                parameters,
            )

        @property
        def in_transaction(self):
            return self._connection.in_transaction

        def close(self):
            self._connection.close()

    def connect_with_hidden_precheck(path):
        return ConnectionProxy(
            original_connect(path)
        )

    monkeypatch.setattr(
        "execution_evidence."
        "sqlite_workspace_membership_store."
        "connect_execution_evidence_database",
        connect_with_hidden_precheck,
    )

    with pytest.raises(
        WorkspaceMembershipAlreadyExistsError,
        match="already exists",
    ):
        store.create(
            _membership(
                workspace_id="workspace-one",
                principal_id=principal_id,
            )
        )


def test_workspace_scope_does_not_disclose_membership(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    first = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )
    second = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-two",
    )

    membership = first.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    with pytest.raises(
        WorkspaceMembershipNotFoundError,
        match="does not exist",
    ):
        second.load_by_id(
            membership.membership_id
        )

    with pytest.raises(
        WorkspaceMembershipNotFoundError,
        match="does not exist",
    ):
        second.load_current(
            principal_id
        )


def test_require_active_rejects_suspended_member(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    store.transition_status(
        membership.membership_id,
        new_status="suspended",
        changed_at=NOW + timedelta(minutes=1),
        expected_revision=0,
    )

    with pytest.raises(
        WorkspaceMembershipInactiveError,
        match="not active",
    ):
        store.require_active(
            principal_id
        )


def test_transition_status_updates_authoritative_cache(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    changed_at = NOW + timedelta(minutes=1)

    result = store.transition_status(
        membership.membership_id,
        new_status="suspended",
        changed_at=changed_at,
        expected_revision=0,
        reason=" temporary hold ",
    )

    assert result.membership.status == (
        "suspended"
    )
    assert result.membership.revision == 1
    assert (
        result.membership.status_changed_at
        == changed_at
    )

    assert (
        result.transition.previous_status
        == "active"
    )
    assert (
        result.transition.new_status
        == "suspended"
    )
    assert result.transition.previous_revision == 0
    assert result.transition.resulting_revision == 1
    assert result.transition.reason == (
        "temporary hold"
    )


def test_self_transition_is_rejected(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    with pytest.raises(
        WorkspaceMembershipTransitionError,
        match="self-transitions",
    ):
        store.transition_status(
            membership.membership_id,
            new_status="active",
            changed_at=NOW,
            expected_revision=0,
        )

    loaded = store.load_by_id(
        membership.membership_id
    )

    assert loaded.status == "active"
    assert loaded.revision == 0
    assert len(
        store.list_transitions(
            membership.membership_id
        )
    ) == 1


def test_removed_membership_is_terminal(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    removed = store.transition_status(
        membership.membership_id,
        new_status="removed",
        changed_at=NOW + timedelta(minutes=1),
        expected_revision=0,
    )

    assert removed.membership.status == "removed"
    assert removed.membership.revision == 1

    with pytest.raises(
        WorkspaceMembershipTransitionError,
        match="not allowed",
    ):
        store.transition_status(
            membership.membership_id,
            new_status="active",
            changed_at=NOW + timedelta(minutes=2),
            expected_revision=1,
        )


def test_removed_membership_allows_new_period(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    first = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    store.transition_status(
        first.membership_id,
        new_status="removed",
        changed_at=NOW + timedelta(minutes=1),
        expected_revision=0,
    )

    second = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    assert (
        second.membership_id
        != first.membership_id
    )
    assert second.status == "active"
    assert second.revision == 0

    assert (
        store.load_current(
            principal_id
        ).membership_id
        == second.membership_id
    )


def test_stale_revision_is_rejected(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = store.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    store.transition_status(
        membership.membership_id,
        new_status="suspended",
        changed_at=NOW + timedelta(minutes=1),
        expected_revision=0,
    )

    with pytest.raises(
        WorkspaceMembershipRevisionConflictError,
        match="expected 0, found 1",
    ):
        store.transition_status(
            membership.membership_id,
            new_status="removed",
            changed_at=NOW + timedelta(minutes=2),
            expected_revision=0,
        )

    current = store.load_by_id(
        membership.membership_id
    )

    assert current.status == "suspended"
    assert current.revision == 1
    assert len(
        store.list_transitions(
            membership.membership_id
        )
    ) == 2


def test_concurrent_transitions_allow_one_writer(
    tmp_path: Path,
):
    database_path, principal_id = _setup(
        tmp_path
    )

    creator = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    membership = creator.create(
        _membership(
            workspace_id="workspace-one",
            principal_id=principal_id,
        )
    )

    barrier = Barrier(2)

    def transition(new_status):
        store = SQLiteWorkspaceMembershipStore(
            database_path,
            workspace_id="workspace-one",
        )

        barrier.wait()

        try:
            result = store.transition_status(
                membership.membership_id,
                new_status=new_status,
                changed_at=(
                    NOW
                    + timedelta(minutes=1)
                ),
                expected_revision=0,
            )
            return (
                "success",
                result.membership.status,
            )
        except (
            WorkspaceMembershipRevisionConflictError
        ) as error:
            return (
                "conflict",
                str(error),
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        results = list(
            executor.map(
                transition,
                (
                    "suspended",
                    "removed",
                ),
            )
        )

    successes = [
        value
        for outcome, value in results
        if outcome == "success"
    ]
    conflicts = [
        value
        for outcome, value in results
        if outcome == "conflict"
    ]

    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0] == (
        "Workspace membership revision conflict: "
        "expected 0, found 1."
    )

    current = creator.load_by_id(
        membership.membership_id
    )

    assert current.revision == 1
    assert current.status in {
        "suspended",
        "removed",
    }

    assert len(
        creator.list_transitions(
            membership.membership_id
        )
    ) == 2


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"

    store = SQLiteWorkspaceMembershipStore(
        database_path,
        workspace_id="workspace-one",
    )

    with pytest.raises(
        WorkspaceMembershipStoreError,
    ):
        store.load_current(
            create_principal_id()
        )
