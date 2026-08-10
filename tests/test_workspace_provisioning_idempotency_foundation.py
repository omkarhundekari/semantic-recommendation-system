from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from pathlib import Path

import pytest

from execution_evidence.principal import Principal
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
)


NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)

IDEMPOTENCY_KEY = "workspace-create-request-1"
OPERATION = "workspace.provision.v1"
FINGERPRINT = "a" * 64


def _database(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"

    version = initialize_execution_evidence_database(
        path
    )

    assert version == CURRENT_SQLITE_SCHEMA_VERSION
    assert version == 24

    return path


def _principal(
    path: Path,
) -> None:
    SQLitePrincipalStore(path).create(
        Principal(
            principal_id=PRINCIPAL_ID,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _provision_graph(
    path: Path,
):
    _principal(path)

    return SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
        reason="idempotency foundation",
    )


def _insert_ledger(
    path: Path,
    result,
) -> None:
    connection = connect_execution_evidence_database(
        path
    )

    try:
        connection.execute(
            """
            INSERT INTO
                workspace_provisioning_idempotency (
                    principal_id,
                    idempotency_key,
                    operation,
                    request_fingerprint,
                    workspace_id,
                    membership_id,
                    owner_role_transition_id,
                    created_at
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                PRINCIPAL_ID,
                IDEMPOTENCY_KEY,
                OPERATION,
                FINGERPRINT,
                result.workspace.workspace_id,
                result.membership.membership_id,
                result.owner_transition.transition_id,
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def test_schema_version_is_23():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 24


def test_fresh_database_has_provisioning_idempotency_ledger(
    tmp_path: Path,
):
    path = _database(tmp_path)

    connection = connect_execution_evidence_database(
        path
    )

    try:
        columns = {
            row["name"]: row
            for row in connection.execute(
                """
                PRAGMA table_info(
                    workspace_provisioning_idempotency
                )
                """
            )
        }

        assert set(columns) == {
            "provisioning_idempotency_row_id",
            "principal_id",
            "idempotency_key",
            "operation",
            "request_fingerprint",
            "workspace_id",
            "membership_id",
            "owner_role_transition_id",
            "created_at",
        }

        indexes = {
            row["name"]
            for row in connection.execute(
                """
                PRAGMA index_list(
                    workspace_provisioning_idempotency
                )
                """
            )
        }

        assert (
            "idx_workspace_provisioning_idempotency_workspace"
            in indexes
        )

        triggers = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE
                    type = 'trigger'
                    AND tbl_name =
                        'workspace_provisioning_idempotency'
                """
            )
        }

        assert (
            "prevent_workspace_provisioning_idempotency_update"
            in triggers
        )
        assert (
            "prevent_workspace_provisioning_idempotency_delete"
            in triggers
        )
    finally:
        connection.close()


def test_ledger_accepts_authoritative_provisioning_graph(
    tmp_path: Path,
):
    path = _database(tmp_path)
    result = _provision_graph(path)

    _insert_ledger(
        path,
        result,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        row = connection.execute(
            """
            SELECT
                principal_id,
                idempotency_key,
                operation,
                request_fingerprint,
                workspace_id,
                membership_id,
                owner_role_transition_id,
                created_at
            FROM workspace_provisioning_idempotency
            WHERE
                principal_id = ?
                AND idempotency_key = ?
            """,
            (
                PRINCIPAL_ID,
                IDEMPOTENCY_KEY,
            ),
        ).fetchone()
    finally:
        connection.close()

    assert row is not None
    assert row["principal_id"] == PRINCIPAL_ID
    assert row["idempotency_key"] == IDEMPOTENCY_KEY
    assert row["operation"] == OPERATION
    assert row["request_fingerprint"] == FINGERPRINT
    assert (
        row["workspace_id"]
        == result.workspace.workspace_id
    )
    assert (
        row["membership_id"]
        == result.membership.membership_id
    )
    assert (
        row["owner_role_transition_id"]
        == result.owner_transition.transition_id
    )
    assert row["created_at"] == NOW.isoformat()


def test_same_principal_and_key_is_unique(
    tmp_path: Path,
):
    path = _database(tmp_path)
    result = _provision_graph(path)

    _insert_ledger(
        path,
        result,
    )

    second = SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO
                    workspace_provisioning_idempotency (
                        principal_id,
                        idempotency_key,
                        operation,
                        request_fingerprint,
                        workspace_id,
                        membership_id,
                        owner_role_transition_id,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PRINCIPAL_ID,
                    IDEMPOTENCY_KEY,
                    OPERATION,
                    "b" * 64,
                    second.workspace.workspace_id,
                    second.membership.membership_id,
                    (
                        second.owner_transition
                        .transition_id
                    ),
                    NOW.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_graph_identities_cannot_be_claimed_twice(
    tmp_path: Path,
):
    path = _database(tmp_path)
    result = _provision_graph(path)

    _insert_ledger(
        path,
        result,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO
                    workspace_provisioning_idempotency (
                        principal_id,
                        idempotency_key,
                        operation,
                        request_fingerprint,
                        workspace_id,
                        membership_id,
                        owner_role_transition_id,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PRINCIPAL_ID,
                    "different-key",
                    OPERATION,
                    "c" * 64,
                    result.workspace.workspace_id,
                    result.membership.membership_id,
                    (
                        result.owner_transition
                        .transition_id
                    ),
                    NOW.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_ledger_rejects_orphan_graph_identity(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path)

    connection = connect_execution_evidence_database(
        path
    )

    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO
                    workspace_provisioning_idempotency (
                        principal_id,
                        idempotency_key,
                        operation,
                        request_fingerprint,
                        workspace_id,
                        membership_id,
                        owner_role_transition_id,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    PRINCIPAL_ID,
                    IDEMPOTENCY_KEY,
                    OPERATION,
                    FINGERPRINT,
                    (
                        "wsp_123e4567-e89b-"
                        "42d3-a456-426614174000"
                    ),
                    (
                        "wsm_123e4567-e89b-"
                        "42d3-a456-426614174000"
                    ),
                    (
                        "wmr_123e4567-e89b-"
                        "42d3-a456-426614174000"
                    ),
                    NOW.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_ledger_is_immutable(
    tmp_path: Path,
):
    path = _database(tmp_path)
    result = _provision_graph(path)

    _insert_ledger(
        path,
        result,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE workspace_provisioning_idempotency
                SET request_fingerprint = ?
                WHERE
                    principal_id = ?
                    AND idempotency_key = ?
                """,
                (
                    "d" * 64,
                    PRINCIPAL_ID,
                    IDEMPOTENCY_KEY,
                ),
            )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM workspace_provisioning_idempotency
                WHERE
                    principal_id = ?
                    AND idempotency_key = ?
                """,
                (
                    PRINCIPAL_ID,
                    IDEMPOTENCY_KEY,
                ),
            )
    finally:
        connection.close()


def test_different_principals_may_reuse_same_key(
    tmp_path: Path,
):
    path = _database(tmp_path)

    second_principal_id = (
        "prn_123e4567-e89b-42d3-a456-426614174001"
    )

    _principal(path)

    SQLitePrincipalStore(path).create(
        Principal(
            principal_id=second_principal_id,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )

    first = SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=PRINCIPAL_ID,
        created_at=NOW,
    )

    second = SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=second_principal_id,
        created_at=NOW,
    )

    connection = connect_execution_evidence_database(
        path
    )

    try:
        for (
            principal_id,
            result,
            fingerprint,
        ) in (
            (
                PRINCIPAL_ID,
                first,
                "e" * 64,
            ),
            (
                second_principal_id,
                second,
                "f" * 64,
            ),
        ):
            connection.execute(
                """
                INSERT INTO
                    workspace_provisioning_idempotency (
                        principal_id,
                        idempotency_key,
                        operation,
                        request_fingerprint,
                        workspace_id,
                        membership_id,
                        owner_role_transition_id,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id,
                    IDEMPOTENCY_KEY,
                    OPERATION,
                    fingerprint,
                    result.workspace.workspace_id,
                    result.membership.membership_id,
                    (
                        result.owner_transition
                        .transition_id
                    ),
                    NOW.isoformat(),
                ),
            )

        count = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM workspace_provisioning_idempotency
            WHERE idempotency_key = ?
            """,
            (IDEMPOTENCY_KEY,),
        ).fetchone()["count"]
    finally:
        connection.close()

    assert int(count) == 2
