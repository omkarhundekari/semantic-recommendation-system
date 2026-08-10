from concurrent.futures import (
    ThreadPoolExecutor,
)
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest

import execution_evidence.workspace_provisioning as provisioning
from execution_evidence.principal import Principal
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
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
    WorkspaceProvisioningIdempotencyConflictError,
    WorkspaceProvisioningPrincipalUnavailableError,
)


NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_A = (
    "prn_123e4567-e89b-42d3-a456-426614174010"
)
PRINCIPAL_B = (
    "prn_123e4567-e89b-42d3-a456-426614174011"
)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _principal(
    path: Path,
    principal_id: str,
):
    return SQLitePrincipalStore(path).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _count(
    path: Path,
    table: str,
) -> int:
    allowed = {
        "workspaces",
        "workspace_memberships",
        "workspace_membership_status_transitions",
        "workspace_membership_role_transitions",
        "workspace_provisioning_idempotency",
    }

    if table not in allowed:
        raise ValueError("Unexpected table.")

    connection = connect_execution_evidence_database(
        path
    )

    try:
        return int(
            connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM {table}
                """
            ).fetchone()["count"]
        )
    finally:
        connection.close()


def test_exact_idempotent_replay_returns_same_graph(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    first = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="provision-001",
        created_at=NOW,
        reason="  first workspace  ",
    )

    second = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="provision-001",
        created_at=NOW + timedelta(hours=1),
        reason="first workspace",
    )

    assert first.replayed is False
    assert second.replayed is True

    assert (
        second.result.workspace.workspace_id
        == first.result.workspace.workspace_id
    )
    assert (
        second.result.membership.membership_id
        == first.result.membership.membership_id
    )
    assert (
        second.result.owner_transition.transition_id
        == first.result.owner_transition.transition_id
    )

    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 1
    )
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 1
    )


def test_idempotency_key_reuse_with_different_request_conflicts(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="same-key",
        created_at=NOW,
        reason="one",
    )

    with pytest.raises(
        WorkspaceProvisioningIdempotencyConflictError,
        match="different request content",
    ):
        service.provision_idempotent(
            principal_id=PRINCIPAL_A,
            idempotency_key="same-key",
            created_at=NOW,
            reason="two",
        )

    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 1
    )


def test_replay_does_not_revalidate_current_principal_status(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    first = service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="deactivated-replay",
        created_at=NOW,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            UPDATE principals
            SET
                status = 'deactivated',
                updated_at = ?
            WHERE principal_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(seconds=1)
                ).isoformat(),
                PRINCIPAL_A,
            ),
        )
    finally:
        connection.close()

    replay = service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="deactivated-replay",
        created_at=NOW + timedelta(hours=1),
    )

    assert replay.replayed is True
    assert (
        replay.result.workspace.workspace_id
        == first.result.workspace.workspace_id
    )


def test_new_creation_requires_current_active_principal(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            UPDATE principals
            SET
                status = 'suspended',
                updated_at = ?
            WHERE principal_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(seconds=1)
                ).isoformat(),
                PRINCIPAL_A,
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        WorkspaceProvisioningPrincipalUnavailableError,
    ):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision_idempotent(
            principal_id=PRINCIPAL_A,
            idempotency_key="new-after-suspend",
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 0
    )


def test_failed_creation_does_not_poison_idempotency_key(
    tmp_path: Path,
    monkeypatch,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    original = (
        provisioning
        .create_workspace_membership_role_transition_id
    )

    monkeypatch.setattr(
        provisioning,
        "create_workspace_membership_role_transition_id",
        lambda: "invalid-transition-id",
    )

    with pytest.raises(Exception):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision_idempotent(
            principal_id=PRINCIPAL_A,
            idempotency_key="retry-after-failure",
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 0
    )

    monkeypatch.setattr(
        provisioning,
        "create_workspace_membership_role_transition_id",
        original,
    )

    result = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="retry-after-failure",
        created_at=NOW,
    )

    assert result.replayed is False
    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 1
    )


def test_same_key_survives_service_restart(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    first = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="restart-key",
        created_at=NOW,
    )

    del first

    replay = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="restart-key",
        created_at=NOW + timedelta(days=1),
    )

    assert replay.replayed is True
    assert _count(path, "workspaces") == 1


def test_different_principals_can_reuse_same_key(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    first = service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="shared-key",
        created_at=NOW,
    )

    second = service.provision_idempotent(
        principal_id=PRINCIPAL_B,
        idempotency_key="shared-key",
        created_at=NOW,
    )

    assert first.replayed is False
    assert second.replayed is False
    assert (
        first.result.workspace.workspace_id
        != second.result.workspace.workspace_id
    )
    assert _count(path, "workspaces") == 2
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 2
    )


def test_concurrent_same_key_creates_exactly_one_graph(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    barrier = Barrier(2)

    def provision():
        barrier.wait()

        return SQLiteWorkspaceProvisioningService(
            path
        ).provision_idempotent(
            principal_id=PRINCIPAL_A,
            idempotency_key="concurrent-key",
            created_at=NOW,
            reason="concurrent",
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as pool:
        results = list(
            pool.map(
                lambda _: provision(),
                range(2),
            )
        )

    assert sorted(
        result.replayed
        for result in results
    ) == [
        False,
        True,
    ]

    workspace_ids = {
        result.result.workspace.workspace_id
        for result in results
    }

    membership_ids = {
        result.result.membership.membership_id
        for result in results
    }

    transition_ids = {
        (
            result
            .result
            .owner_transition
            .transition_id
        )
        for result in results
    }

    assert len(workspace_ids) == 1
    assert len(membership_ids) == 1
    assert len(transition_ids) == 1

    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_memberships",
        )
        == 1
    )
    assert (
        _count(
            path,
            "workspace_membership_status_transitions",
        )
        == 1
    )
    assert (
        _count(
            path,
            "workspace_membership_role_transitions",
        )
        == 1
    )
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 1
    )


def test_real_ledger_graph_passes_foreign_key_check(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    result = SQLiteWorkspaceProvisioningService(
        path
    ).provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="fk-check",
        created_at=NOW,
    )

    assert result.replayed is False

    connection = connect_execution_evidence_database(
        path
    )

    try:
        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    finally:
        connection.close()

    assert violations == []


@pytest.mark.parametrize(
    "idempotency_key",
    [
        "",
        "x" * 256,
    ],
)
def test_invalid_idempotency_key_is_rejected(
    tmp_path: Path,
    idempotency_key: str,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    with pytest.raises(ValueError):
        SQLiteWorkspaceProvisioningService(
            path
        ).provision_idempotent(
            principal_id=PRINCIPAL_A,
            idempotency_key=idempotency_key,
            created_at=NOW,
        )

    assert _count(path, "workspaces") == 0


def test_request_fingerprint_is_stable_and_lowercase_hex():
    first = (
        SQLiteWorkspaceProvisioningService
        ._provisioning_request_fingerprint(
            principal_id=PRINCIPAL_A,
            normalized_reason="reason",
        )
    )

    second = (
        SQLiteWorkspaceProvisioningService
        ._provisioning_request_fingerprint(
            principal_id=PRINCIPAL_A,
            normalized_reason="reason",
        )
    )

    assert first == second
    assert len(first) == 64
    assert first == first.lower()
    assert set(first) <= set(
        "0123456789abcdef"
    )

def test_replay_survives_legitimate_membership_state_evolution(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    service = SQLiteWorkspaceProvisioningService(
        path
    )

    first = service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="replay-after-state-change",
        created_at=NOW,
        reason="original provisioning",
    )

    original_workspace_id = (
        first.result.workspace.workspace_id
    )
    original_membership_id = (
        first.result.membership.membership_id
    )
    original_owner_transition_id = (
        first.result.owner_transition.transition_id
    )

    membership_store = (
        SQLiteWorkspaceMembershipStore(
            path,
            workspace_id=original_workspace_id,
        )
    )

    # Add a second active member so the original owner can
    # evolve without violating the last-manager invariant.
    second_membership = (
        membership_store.create(
            WorkspaceMembership(
                membership_id=(
                    create_workspace_membership_id()
                ),
                workspace_id=original_workspace_id,
                principal_id=PRINCIPAL_B,
                status="active",
                role=None,
                revision=0,
                created_by_principal_id=PRINCIPAL_A,
                created_at=(
                    NOW + timedelta(seconds=1)
                ),
                updated_at=(
                    NOW + timedelta(seconds=1)
                ),
                status_changed_at=(
                    NOW + timedelta(seconds=1)
                ),
            )
        )
    )

    assert second_membership.role is None
    assert second_membership.revision == 0

    promoted = membership_store.transition_role(
        second_membership.membership_id,
        new_role="admin",
        changed_at=NOW + timedelta(seconds=2),
        expected_revision=0,
        changed_by_principal_id=PRINCIPAL_A,
        reason="add second workspace manager",
    )

    assert promoted.membership.role == "admin"
    assert promoted.membership.revision == 1

    changed = membership_store.transition_status(
        original_membership_id,
        new_status="suspended",
        changed_at=NOW + timedelta(seconds=3),
        expected_revision=1,
        reason="legitimate membership evolution",
        changed_by_principal_id=PRINCIPAL_B,
    )

    assert changed.membership.status == "suspended"
    assert changed.membership.role == "owner"
    assert changed.membership.revision == 2

    replay = service.provision_idempotent(
        principal_id=PRINCIPAL_A,
        idempotency_key="replay-after-state-change",
        created_at=NOW + timedelta(days=30),
        reason="original provisioning",
    )

    assert replay.replayed is True

    assert (
        replay.result.workspace.workspace_id
        == original_workspace_id
    )
    assert (
        replay.result.membership.membership_id
        == original_membership_id
    )
    assert (
        replay.result.owner_transition.transition_id
        == original_owner_transition_id
    )

    # Replay validates durable provisioning identity and
    # historical linkage, not mutable current membership state.
    assert replay.result.membership.status == "suspended"
    assert replay.result.membership.role == "owner"
    assert replay.result.membership.revision == 2

    # The original provisioning edge remains immutable even
    # though current membership state has legitimately evolved.
    assert (
        replay.result.owner_transition.previous_role
        is None
    )
    assert (
        replay.result.owner_transition.new_role
        == "owner"
    )
    assert (
        replay.result.owner_transition.previous_revision
        == 0
    )
    assert (
        replay.result.owner_transition.resulting_revision
        == 1
    )
    assert (
        replay.result.owner_transition
        .changed_by_principal_id
        is None
    )

    assert _count(path, "workspaces") == 1
    assert (
        _count(
            path,
            "workspace_provisioning_idempotency",
        )
        == 1
    )
