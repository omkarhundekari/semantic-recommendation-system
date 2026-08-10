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
from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.principal import Principal
from execution_evidence.project_discovery import (
    MAX_PROJECT_DISCOVERY_CURSOR_BYTES,
    MAX_PROJECT_DISCOVERY_RESULTS,
    SQLiteProjectDiscoveryService,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.workspace_provisioning import (
    SQLiteWorkspaceProvisioningService,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
)

from product_api import (
    app,
    get_authorized_workspace_context,
    get_project_discovery_service,
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
    path = tmp_path / "project-discovery.db"

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


def _workspace(
    path: Path,
    principal_id: str,
):
    return SQLiteWorkspaceProvisioningService(
        path
    ).provision(
        principal_id=principal_id,
        created_at=NOW,
    )


def _insert_project(
    path: Path,
    *,
    workspace_id: str,
    project_id: str,
    created_at: datetime,
    status: str = "active",
    title: str | None = None,
) -> None:
    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO projects (
                project_id,
                workspace_id,
                title,
                status,
                created_at,
                updated_at,
                revision
            )
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                project_id,
                workspace_id,
                title or project_id,
                status,
                created_at.isoformat(),
                created_at.isoformat(),
            ),
        )
    finally:
        connection.close()


def _project_ids(result):
    return [
        project.project_id
        for project in result.projects
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


def test_discovers_only_active_projects_in_workspace(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    workspace_a = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    workspace_b = _workspace(
        path,
        PRINCIPAL_B,
    ).workspace.workspace_id

    _insert_project(
        path,
        workspace_id=workspace_a,
        project_id="proj_active_a",
        created_at=NOW,
    )

    _insert_project(
        path,
        workspace_id=workspace_a,
        project_id="proj_archived_a",
        created_at=NOW + timedelta(seconds=1),
        status="archived",
    )

    _insert_project(
        path,
        workspace_id=workspace_b,
        project_id="proj_active_b",
        created_at=NOW + timedelta(seconds=2),
    )

    result = SQLiteProjectDiscoveryService(
        path
    ).discover(
        workspace_id=workspace_a
    )

    assert _project_ids(result) == [
        "proj_active_a"
    ]

    assert result.truncated is False
    assert result.next_cursor is None


def test_exact_page_boundary_has_no_next_cursor(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    for index in range(3):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=f"proj_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    result = SQLiteProjectDiscoveryService(
        path
    ).discover(
        workspace_id=workspace_id,
        page_size=3,
    )

    assert len(result.projects) == 3
    assert result.truncated is False
    assert result.next_cursor is None


def test_page_plus_one_returns_cursor_and_remainder(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    for index in range(3):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=f"proj_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    service = SQLiteProjectDiscoveryService(
        path
    )

    first = service.discover(
        workspace_id=workspace_id,
        page_size=2,
    )

    assert first.truncated is True
    assert first.next_cursor is not None
    assert _project_ids(first) == [
        "proj_2",
        "proj_1",
    ]

    second = service.discover(
        workspace_id=workspace_id,
        cursor=first.next_cursor,
        page_size=2,
    )

    assert _project_ids(second) == [
        "proj_0"
    ]
    assert second.truncated is False
    assert second.next_cursor is None


def test_full_static_traversal_returns_every_project_once(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    expected = set()

    for index in range(11):
        project_id = f"proj_{index:02d}"
        expected.add(project_id)

        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=project_id,
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    service = SQLiteProjectDiscoveryService(
        path
    )

    seen = []
    cursor = None

    while True:
        result = service.discover(
            workspace_id=workspace_id,
            cursor=cursor,
            page_size=3,
        )

        seen.extend(
            _project_ids(result)
        )

        if result.next_cursor is None:
            break

        cursor = result.next_cursor

    assert len(seen) == 11
    assert len(set(seen)) == 11
    assert set(seen) == expected


@pytest.mark.parametrize(
    "cursor",
    [
        "%%%",
        _encode_raw([]),
        _encode_raw(
            {
                "v": 2,
                "created_at": NOW.isoformat(),
                "project_id": "proj_test",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "project_id": "proj_test",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "created_at": "not-a-time",
                "project_id": "proj_test",
            }
        ),
        _encode_raw(
            {
                "v": 1,
                "created_at": NOW.isoformat(),
                "project_id": "",
            }
        ),
    ],
)
def test_malformed_cursor_is_rejected(
    tmp_path: Path,
    cursor: str,
):
    path = _database(tmp_path)

    with pytest.raises(ValueError):
        SQLiteProjectDiscoveryService(
            path
        ).discover(
            workspace_id="workspace-test",
            cursor=cursor,
            page_size=10,
        )


def test_oversized_cursor_is_rejected_before_decode(
    tmp_path: Path,
):
    path = _database(tmp_path)

    cursor = (
        "A"
        * (
            MAX_PROJECT_DISCOVERY_CURSOR_BYTES
            + 1
        )
    )

    with pytest.raises(
        ValueError,
        match="exceeds",
    ):
        SQLiteProjectDiscoveryService(
            path
        ).discover(
            workspace_id="workspace-test",
            cursor=cursor,
        )


def test_cursor_from_workspace_a_cannot_grant_a_scope_to_b(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)
    _principal(path, PRINCIPAL_B)

    workspace_a = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    workspace_b = _workspace(
        path,
        PRINCIPAL_B,
    ).workspace.workspace_id

    for index in range(4):
        _insert_project(
            path,
            workspace_id=workspace_a,
            project_id=f"proj_a_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

        _insert_project(
            path,
            workspace_id=workspace_b,
            project_id=f"proj_b_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    service = SQLiteProjectDiscoveryService(
        path
    )

    page_a = service.discover(
        workspace_id=workspace_a,
        page_size=2,
    )

    assert page_a.next_cursor is not None

    page_b = service.discover(
        workspace_id=workspace_b,
        cursor=page_a.next_cursor,
        page_size=10,
    )

    assert all(
        project.project_id.startswith(
            "proj_b_"
        )
        for project in page_b.projects
    )


def test_project_cursor_identity_is_immutable(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    _insert_project(
        path,
        workspace_id=workspace_id,
        project_id="proj_immutable",
        created_at=NOW,
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
                "Project discovery identity "
                "fields are immutable"
            ),
        ):
            connection.execute(
                """
                UPDATE projects
                SET created_at = ?
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                """,
                (
                    (
                        NOW
                        + timedelta(seconds=1)
                    ).isoformat(),
                    workspace_id,
                    "proj_immutable",
                ),
            )
    finally:
        connection.close()


def test_continuation_query_uses_project_discovery_index_without_temp_sort(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    for index in range(3):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=f"proj_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    boundary_created_at = (
        NOW + timedelta(seconds=1)
    ).isoformat()

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        first_rows = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                project.project_id
            FROM projects AS project
            WHERE
                project.workspace_id = ?
                AND project.status = 'active'
            ORDER BY
                project.created_at DESC,
                project.project_id ASC
            LIMIT ?
            """,
            (
                workspace_id,
                3,
            ),
        ).fetchall()

        continuation_rows = connection.execute(
            """
            EXPLAIN QUERY PLAN
            SELECT
                project.project_id
            FROM projects AS project
            WHERE
                project.workspace_id = ?
                AND project.status = 'active'
                AND (
                    project.created_at < ?
                    OR (
                        project.created_at = ?
                        AND project.project_id > ?
                    )
                )
            ORDER BY
                project.created_at DESC,
                project.project_id ASC
            LIMIT ?
            """,
            (
                workspace_id,
                boundary_created_at,
                boundary_created_at,
                "proj_1",
                3,
            ),
        ).fetchall()

        for rows in (
            first_rows,
            continuation_rows,
        ):
            details = [
                str(row["detail"])
                for row in rows
            ]

            assert any(
                "idx_projects_workspace_discovery"
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


def test_api_requires_project_read_capability_before_listing(
    tmp_path: Path,
):
    path = _database(tmp_path)

    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_A,
        membership_id=(
            "wsm_123e4567-e89b-42d3-a456-"
            "426614174003"
        ),
        membership_role=None,
        workspace_id="workspace-test",
    )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_discovery_service
    ] = lambda: SQLiteProjectDiscoveryService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces/workspace-test/projects"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert "project.read" in response.json()[
        "detail"
    ]


def test_api_passes_explicit_max_page_size_to_discovery_service(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)

    provisioned = _workspace(
        path,
        PRINCIPAL_A,
    )

    workspace_id = (
        provisioned.workspace.workspace_id
    )

    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_A,
        membership_id=(
            provisioned.membership.membership_id
        ),
        membership_role=(
            provisioned.membership.role
        ),
        workspace_id=workspace_id,
    )

    class SpyProjectDiscoveryService(
        SQLiteProjectDiscoveryService
    ):
        def __init__(self, database_path):
            super().__init__(database_path)
            self.received_page_size = None
            self.received_cursor = object()

        def discover(
            self,
            *,
            workspace_id: str,
            cursor=None,
            page_size=None,
        ):
            self.received_page_size = page_size
            self.received_cursor = cursor

            return super().discover(
                workspace_id=workspace_id,
                cursor=cursor,
                page_size=page_size,
            )

    service = SpyProjectDiscoveryService(
        path
    )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_discovery_service
    ] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get(
                (
                    f"/v1/workspaces/"
                    f"{workspace_id}/projects"
                ),
                params={
                    "page_size": (
                        MAX_PROJECT_DISCOVERY_RESULTS
                    ),
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    assert (
        service.received_page_size
        == MAX_PROJECT_DISCOVERY_RESULTS
    )

    assert service.received_cursor is None


def test_api_preserves_array_body_and_exposes_continuation_headers(
    tmp_path: Path,
):
    path = _database(tmp_path)

    _principal(path, PRINCIPAL_A)

    provisioned = _workspace(
        path,
        PRINCIPAL_A,
    )

    workspace_id = (
        provisioned.workspace.workspace_id
    )

    for index in range(3):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=f"proj_{index}",
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_A,
        membership_id=(
            provisioned.membership.membership_id
        ),
        membership_role=(
            provisioned.membership.role
        ),
        workspace_id=workspace_id,
    )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_discovery_service
    ] = lambda: SQLiteProjectDiscoveryService(
        path
    )

    try:
        with TestClient(app) as client:
            first = client.get(
                (
                    f"/v1/workspaces/"
                    f"{workspace_id}/projects"
                ),
                params={
                    "page_size": 2,
                },
            )

            assert first.status_code == 200

            cursor = first.headers[
                "Project-Discovery-Next-Cursor"
            ]

            second = client.get(
                (
                    f"/v1/workspaces/"
                    f"{workspace_id}/projects"
                ),
                params={
                    "page_size": 2,
                    "cursor": cursor,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert isinstance(first.json(), list)
    assert len(first.json()) == 2

    assert (
        first.headers[
            "Project-Discovery-Truncated"
        ]
        == "true"
    )

    assert second.status_code == 200
    assert isinstance(second.json(), list)
    assert len(second.json()) == 1

    ids = [
        item["project_id"]
        for item in (
            first.json()
            + second.json()
        )
    ]

    assert len(ids) == 3
    assert len(set(ids)) == 3


def test_api_malformed_cursor_returns_422(
    tmp_path: Path,
):
    path = _database(tmp_path)

    context = AuthorizedWorkspaceContext(
        principal_id=PRINCIPAL_A,
        membership_id=(
            "wsm_123e4567-e89b-42d3-a456-"
            "426614174003"
        ),
        membership_role="owner",
        workspace_id="workspace-test",
    )

    app.dependency_overrides[
        get_authorized_workspace_context
    ] = lambda: context

    app.dependency_overrides[
        get_project_discovery_service
    ] = lambda: SQLiteProjectDiscoveryService(
        path
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/workspaces/workspace-test/projects",
                params={
                    "cursor": "%%%",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_project_lifecycle_update_does_not_move_active_project_across_cursor_boundary(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    project_ids = [
        f"proj_lifecycle_{index}"
        for index in range(4)
    ]

    for index, project_id in enumerate(
        project_ids
    ):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=project_id,
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    service = SQLiteProjectDiscoveryService(
        path
    )

    first_page = service.discover(
        workspace_id=workspace_id,
        page_size=2,
    )

    assert len(first_page.projects) == 2
    assert first_page.next_cursor is not None

    first_page_ids = {
        project.project_id
        for project in first_page.projects
    }

    remaining_ids = [
        project_id
        for project_id in project_ids
        if project_id not in first_page_ids
    ]

    assert len(remaining_ids) == 2

    target_project_id = remaining_ids[0]

    registry = SQLiteRoadmapSnapshotRegistry(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
        ensure_workspace=False,
    )

    archived = registry.transition_project_status(
        target_project_id,
        new_status="archived",
        changed_at=(
            NOW + timedelta(hours=1)
        ),
        expected_revision=0,
        reason="pagination lifecycle regression",
    )

    assert archived.changed is True
    assert archived.current_status == "archived"

    reactivated = registry.transition_project_status(
        target_project_id,
        new_status="active",
        changed_at=(
            NOW + timedelta(hours=2)
        ),
        expected_revision=1,
        reason="pagination lifecycle regression",
    )

    assert reactivated.changed is True
    assert reactivated.current_status == "active"

    second_page = service.discover(
        workspace_id=workspace_id,
        cursor=first_page.next_cursor,
        page_size=10,
    )

    traversed_ids = [
        project.project_id
        for project in first_page.projects
    ] + [
        project.project_id
        for project in second_page.projects
    ]

    assert len(traversed_ids) == 4
    assert len(set(traversed_ids)) == 4
    assert set(traversed_ids) == set(
        project_ids
    )


def test_project_archived_between_pages_drops_out_without_duplicate_traversal(
    tmp_path: Path,
):
    path = _database(tmp_path)
    _principal(path, PRINCIPAL_A)

    workspace_id = _workspace(
        path,
        PRINCIPAL_A,
    ).workspace.workspace_id

    project_ids = [
        f"proj_archive_{index}"
        for index in range(4)
    ]

    for index, project_id in enumerate(
        project_ids
    ):
        _insert_project(
            path,
            workspace_id=workspace_id,
            project_id=project_id,
            created_at=(
                NOW + timedelta(seconds=index)
            ),
        )

    service = SQLiteProjectDiscoveryService(
        path
    )

    first_page = service.discover(
        workspace_id=workspace_id,
        page_size=2,
    )

    assert len(first_page.projects) == 2
    assert first_page.next_cursor is not None

    first_page_ids = {
        project.project_id
        for project in first_page.projects
    }

    remaining_ids = [
        project_id
        for project_id in project_ids
        if project_id not in first_page_ids
    ]

    assert len(remaining_ids) == 2

    archived_project_id = remaining_ids[0]

    registry = SQLiteRoadmapSnapshotRegistry(
        path,
        workspace_id=workspace_id,
        initialize_schema=False,
        ensure_workspace=False,
    )

    archived = registry.transition_project_status(
        archived_project_id,
        new_status="archived",
        changed_at=(
            NOW + timedelta(hours=1)
        ),
        expected_revision=0,
        reason="pagination lifecycle regression",
    )

    assert archived.changed is True
    assert archived.current_status == "archived"

    second_page = service.discover(
        workspace_id=workspace_id,
        cursor=first_page.next_cursor,
        page_size=10,
    )

    second_page_ids = {
        project.project_id
        for project in second_page.projects
    }

    assert (
        archived_project_id
        not in second_page_ids
    )

    traversed_ids = [
        project.project_id
        for project in first_page.projects
    ] + [
        project.project_id
        for project in second_page.projects
    ]

    expected_active_ids = (
        set(project_ids)
        - {archived_project_id}
    )

    assert set(traversed_ids) == (
        expected_active_ids
    )
    assert len(traversed_ids) == len(
        set(traversed_ids)
    )

