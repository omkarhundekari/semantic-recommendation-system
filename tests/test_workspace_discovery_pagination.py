from __future__ import annotations

import base64
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal import Principal
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.workspace_discovery import (
    MAX_WORKSPACE_DISCOVERY_CURSOR_BYTES,
    SQLiteWorkspaceDiscoveryService,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
)
from product_api import (
    app,
    get_authenticated_request_principal,
    get_workspace_discovery_service,
)


PRINCIPAL_A = (
    "prn_123e4567-e89b-42d3-a456-4266141740a1"
)
PRINCIPAL_B = (
    "prn_123e4567-e89b-42d3-a456-4266141740b1"
)

NOW = datetime(
    2026,
    8,
    10,
    12,
    0,
    tzinfo=timezone.utc,
)


def _database(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "workspace-pagination.db"
    initialize_execution_evidence_database(
        path
    )
    return path


def _principal(
    path: Path,
    principal_id: str,
) -> None:
    SQLitePrincipalStore(path).create(
        Principal(
            principal_id=principal_id,
            principal_kind="human",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )


def _authenticated(
    principal_id: str,
) -> AuthenticatedRequestPrincipal:
    suffix = (
        "a1"
        if principal_id == PRINCIPAL_A
        else "b1"
    )

    return AuthenticatedRequestPrincipal(
        principal_id=principal_id,
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-4266141740"
            + suffix
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-4266141741"
            + suffix
        ),
        issuer="https://issuer.example",
        subject=f"subject-{principal_id}",
    )


def _provision_many(
    path: Path,
    *,
    principal_id: str,
    count: int,
):
    service = SQLiteWorkspaceProvisioningService(
        path
    )

    return [
        service.provision(
            principal_id=principal_id,
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )
        for index in range(count)
    ]


def _encode_raw(payload) -> str:
    raw = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    return (
        base64.urlsafe_b64encode(raw)
        .decode("ascii")
        .rstrip("=")
    )


def test_exact_page_boundary_has_no_next_cursor(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)
    _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=3,
    )

    result = SQLiteWorkspaceDiscoveryService(
        path
    ).discover(
        principal=_authenticated(PRINCIPAL_A),
        page_size=3,
    )

    assert len(result.workspaces) == 3
    assert result.truncated is False
    assert result.next_cursor is None


def test_n_plus_one_returns_cursor_and_remainder_without_duplicates(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=4,
    )

    service = SQLiteWorkspaceDiscoveryService(
        path
    )

    first = service.discover(
        principal=_authenticated(PRINCIPAL_A),
        page_size=3,
    )

    assert first.truncated is True
    assert first.next_cursor is not None
    assert len(first.workspaces) == 3

    second = service.discover(
        principal=_authenticated(PRINCIPAL_A),
        cursor=first.next_cursor,
        page_size=3,
    )

    assert second.truncated is False
    assert second.next_cursor is None
    assert len(second.workspaces) == 1

    ids = [
        item.workspace_id
        for item in (
            first.workspaces
            + second.workspaces
        )
    ]

    assert len(ids) == 4
    assert len(set(ids)) == 4

    assert set(ids) == {
        item.workspace.workspace_id
        for item in provisioned
    }


def test_static_full_traversal_returns_every_workspace_once(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=9,
    )

    service = SQLiteWorkspaceDiscoveryService(
        path
    )

    cursor = None
    discovered_ids = []

    while True:
        page = service.discover(
            principal=_authenticated(PRINCIPAL_A),
            cursor=cursor,
            page_size=2,
        )

        discovered_ids.extend(
            item.workspace_id
            for item in page.workspaces
        )

        if page.next_cursor is None:
            break

        cursor = page.next_cursor

    assert len(discovered_ids) == 9
    assert len(set(discovered_ids)) == 9

    assert set(discovered_ids) == {
        item.workspace.workspace_id
        for item in provisioned
    }


@pytest.mark.parametrize(
    "cursor",
    [
        "%%%",
        _encode_raw(["not", "an", "object"]),
        _encode_raw(
            {
                "v": 2,
                "created_at": NOW.isoformat(),
                "workspace_id": "workspace",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "workspace_id": "workspace",
            }
        ),
        _encode_raw(
            {
                "v": "1",
                "created_at": NOW.isoformat(),
                "workspace_id": "workspace",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "created_at": "not-a-timestamp",
                "workspace_id": "workspace",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "created_at": NOW.isoformat(),
                "workspace_id": "",
            }
        ),
    ],
)
def test_malformed_cursor_is_rejected(
    tmp_path: Path,
    cursor: str,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    with pytest.raises(ValueError):
        SQLiteWorkspaceDiscoveryService(
            path
        ).discover(
            principal=_authenticated(PRINCIPAL_A),
            cursor=cursor,
            page_size=10,
        )


def test_non_utc_cursor_timestamp_is_rejected(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    cursor = _encode_raw(
        {
            "v": 1,
            "created_at": (
                "2026-08-10T08:00:00-04:00"
            ),
            "workspace_id": (
                "wsp_123e4567-e89b-42d3-a456-"
                "426614174099"
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="must use UTC",
    ):
        SQLiteWorkspaceDiscoveryService(
            path
        ).discover(
            principal=_authenticated(
                PRINCIPAL_A
            ),
            cursor=cursor,
            page_size=10,
        )


def test_oversized_cursor_is_rejected_before_decode(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    cursor = (
        "A"
        * (
            MAX_WORKSPACE_DISCOVERY_CURSOR_BYTES
            + 1
        )
    )

    with pytest.raises(
        ValueError,
        match="exceeds",
    ):
        SQLiteWorkspaceDiscoveryService(
            path
        ).discover(
            principal=_authenticated(PRINCIPAL_A),
            cursor=cursor,
        )


def test_cursor_from_principal_a_never_grants_principal_a_scope_to_b(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=4,
    )

    workspaces_b = _provision_many(
        path,
        principal_id=PRINCIPAL_B,
        count=4,
    )

    service = SQLiteWorkspaceDiscoveryService(
        path
    )

    page_a = service.discover(
        principal=_authenticated(PRINCIPAL_A),
        page_size=2,
    )

    assert page_a.next_cursor is not None

    page_b = service.discover(
        principal=_authenticated(PRINCIPAL_B),
        cursor=page_a.next_cursor,
        page_size=10,
    )

    b_ids = {
        item.workspace.workspace_id
        for item in workspaces_b
    }

    assert {
        item.workspace_id
        for item in page_b.workspaces
    }.issubset(b_ids)


def test_mixed_utc_timestamp_precision_does_not_break_keyset_traversal(
    tmp_path: Path,
):
    """Keyset follows SQLite TEXT order, including mixed precision.

    Semantically equal UTC instants may have different persisted
    textual representations. They are therefore distinct primary
    sort keys, and the continuation predicate must still traverse
    both exactly once.
    """

    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=3,
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        memberships = connection.execute(
            """
            SELECT
                membership_id,
                created_at
            FROM workspace_memberships
            WHERE principal_id = ?
            ORDER BY created_at DESC
            """,
            (PRINCIPAL_A,),
        ).fetchall()

        assert len(memberships) == 3

        # The domain layer normally owns creation timestamps.
        # This deliberate direct-SQL fixture exercises the exact
        # storage representation concern raised during review.
        #
        # Temporarily remove only the immutability trigger so the
        # test can construct legacy/mixed textual representations.
        connection.execute(
            """
            DROP TRIGGER
            prevent_workspace_membership_identity_update
            """
        )

        connection.execute(
            """
            UPDATE workspace_memberships
            SET created_at = ?
            WHERE membership_id = ?
            """,
            (
                "2026-08-10T12:00:00.000000+00:00",
                memberships[0]["membership_id"],
            ),
        )

        connection.execute(
            """
            UPDATE workspace_memberships
            SET created_at = ?
            WHERE membership_id = ?
            """,
            (
                "2026-08-10T12:00:00+00:00",
                memberships[1]["membership_id"],
            ),
        )

        connection.execute(
            """
            UPDATE workspace_memberships
            SET created_at = ?
            WHERE membership_id = ?
            """,
            (
                "2026-08-10T11:59:59.999999+00:00",
                memberships[2]["membership_id"],
            ),
        )

    finally:
        connection.close()

    service = SQLiteWorkspaceDiscoveryService(
        path
    )

    seen = []
    cursor = None

    while True:
        result = service.discover(
            principal=_authenticated(
                PRINCIPAL_A
            ),
            cursor=cursor,
            page_size=1,
        )

        seen.extend(
            item.workspace_id
            for item in result.workspaces
        )

        if result.next_cursor is None:
            break

        cursor = result.next_cursor

    expected = {
        item.workspace.workspace_id
        for item in provisioned
    }

    assert len(seen) == 3
    assert len(set(seen)) == 3
    assert set(seen) == expected



def test_membership_created_at_is_immutable_after_creation(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = (
        SQLiteWorkspaceProvisioningService(
            path
        ).provision(
            principal_id=PRINCIPAL_A,
            created_at=NOW,
        )
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
            match=(
                "Workspace membership identity "
                "fields are immutable"
            ),
        ):
            connection.execute(
                """
                UPDATE workspace_memberships
                SET created_at = ?
                WHERE membership_id = ?
                """,
                (
                    (
                        NOW
                        + timedelta(seconds=1)
                    ).isoformat(),
                    (
                        provisioned
                        .membership
                        .membership_id
                    ),
                ),
            )

        stored = connection.execute(
            """
            SELECT created_at
            FROM workspace_memberships
            WHERE membership_id = ?
            """,
            (
                provisioned
                .membership
                .membership_id,
            ),
        ).fetchone()

        assert stored is not None
        assert (
            stored["created_at"]
            == NOW.isoformat()
        )
    finally:
        connection.close()


def test_paginated_query_uses_stable_discovery_index_without_temp_sort(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=3,
    )

    boundary_created_at = (
        provisioned[-1]
        .membership
        .created_at
        .isoformat()
    )
    boundary_workspace_id = (
        provisioned[-1]
        .workspace
        .workspace_id
    )

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        rows = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                workspace.workspace_id
            FROM principals AS principal
            JOIN workspace_memberships AS membership
                ON
                    membership.principal_id =
                        principal.principal_id
            JOIN workspaces AS workspace
                ON
                    workspace.workspace_id =
                        membership.workspace_id
            WHERE
                principal.principal_id = ?
                AND principal.status = 'active'
                AND membership.status = 'active'
                AND membership.role IS NOT NULL
                AND (
                    membership.created_at < ?
                    OR (
                        membership.created_at = ?
                        AND membership.workspace_id > ?
                    )
                )
            ORDER BY
                membership.created_at DESC,
                membership.workspace_id ASC
            LIMIT ?
            """,
            (
                PRINCIPAL_A,
                boundary_created_at,
                boundary_created_at,
                boundary_workspace_id,
                3,
            ),
        ).fetchall()

        details = [
            str(row["detail"])
            for row in rows
        ]

        assert any(
            "idx_workspace_memberships_principal_discovery_v2"
            in detail
            for detail in details
        )

        assert not any(
            "USE TEMP B-TREE FOR ORDER BY"
            in detail
            for detail in details
        )
    finally:
        connection.close()


def test_api_returns_next_cursor_and_continues(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    provisioned = _provision_many(
        path,
        principal_id=PRINCIPAL_A,
        count=3,
    )

    authenticated = _authenticated(
        PRINCIPAL_A
    )

    service = SQLiteWorkspaceDiscoveryService(
        path
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = lambda: authenticated

    app.dependency_overrides[
        get_workspace_discovery_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            first = client.get(
                "/v1/workspaces",
                params={
                    "page_size": 2,
                },
            )

            assert first.status_code == 200
            assert (
                first.headers[
                    "Workspace-Discovery-Truncated"
                ]
                == "true"
            )

            cursor = first.headers[
                "Workspace-Discovery-Next-Cursor"
            ]

            second = client.get(
                "/v1/workspaces",
                params={
                    "page_size": 2,
                    "cursor": cursor,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert second.status_code == 200
    assert (
        second.headers[
            "Workspace-Discovery-Truncated"
        ]
        == "false"
    )
    assert (
        "Workspace-Discovery-Next-Cursor"
        not in second.headers
    )

    ids = [
        item["workspace_id"]
        for item in (
            first.json()
            + second.json()
        )
    ]

    assert len(ids) == 3
    assert len(set(ids)) == 3

    assert set(ids) == {
        item.workspace.workspace_id
        for item in provisioned
    }


def test_api_malformed_cursor_returns_422(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    authenticated = _authenticated(
        PRINCIPAL_A
    )

    app.dependency_overrides[
        get_authenticated_request_principal
    ] = lambda: authenticated

    app.dependency_overrides[
        get_workspace_discovery_service
    ] = lambda: SQLiteWorkspaceDiscoveryService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces",
                params={
                    "cursor": "%%%",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
