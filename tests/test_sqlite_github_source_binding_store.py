from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution_evidence.github_source_binding import (
    GitHubSourceBinding,
    create_github_source_binding_id,
)
from execution_evidence.github_source_binding_store import (
    GitHubSourceBindingAlreadyExistsError,
    GitHubSourceBindingNotFoundError,
    GitHubSourceBindingProjectNotFoundError,
    GitHubSourceBindingProjectScopeError,
    GitHubSourceBindingStoreError,
    GitHubSourceBindingTransitionError,
    GitHubSourceBindingWorkspaceNotFoundError,
)
from execution_evidence.sqlite_github_source_binding_store import (
    SQLiteGitHubSourceBindingStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _insert_workspace(
    database_path: Path,
    *,
    workspace_id: str,
) -> None:
    connection = connect_execution_evidence_database(
        database_path
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


def _insert_project(
    database_path: Path,
    *,
    workspace_id: str,
    project_id: str,
) -> None:
    connection = connect_execution_evidence_database(
        database_path
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
                updated_at
            )
            VALUES (?, ?, ?, 'active', ?, ?)
            """,
            (
                project_id,
                workspace_id,
                "GitHub binding test project",
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()


def _scope(
    database_path: Path,
    *,
    workspace_id: str = "workspace-a",
    project_id: str = "project-a",
) -> None:
    _insert_workspace(
        database_path,
        workspace_id=workspace_id,
    )
    _insert_project(
        database_path,
        workspace_id=workspace_id,
        project_id=project_id,
    )


def _binding(
    *,
    repository_id: str = "1001",
    workspace_id: str = "workspace-a",
    project_id: str = "project-a",
    installation_id: str | None = "2001",
    binding_id: str | None = None,
    created_at: datetime = NOW,
    retired_at: datetime | None = None,
    retired_reason: str | None = None,
) -> GitHubSourceBinding:
    return GitHubSourceBinding(
        github_source_binding_id=(
            binding_id
            or create_github_source_binding_id()
        ),
        repository_id=repository_id,
        workspace_id=workspace_id,
        project_id=project_id,
        installation_id=installation_id,
        created_at=created_at,
        retired_at=retired_at,
        retired_reason=retired_reason,
    )


def test_create_and_load_binding(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )
    binding = _binding()

    created = store.create(binding)

    assert created == binding
    assert store.load(
        binding.github_source_binding_id
    ) == binding


def test_create_rejects_retired_binding(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )
    binding = _binding(
        retired_at=NOW + timedelta(minutes=1),
        retired_reason="repository moved",
    )

    with pytest.raises(
        GitHubSourceBindingTransitionError,
    ):
        store.create(binding)


def test_create_requires_existing_workspace(
    database_path: Path,
):
    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingWorkspaceNotFoundError,
    ):
        store.create(_binding())


def test_create_requires_existing_project(
    database_path: Path,
):
    _insert_workspace(
        database_path,
        workspace_id="workspace-a",
    )

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingProjectNotFoundError,
    ):
        store.create(_binding())


def test_create_rejects_project_from_other_workspace(
    database_path: Path,
):
    _insert_workspace(
        database_path,
        workspace_id="workspace-a",
    )
    _insert_workspace(
        database_path,
        workspace_id="workspace-b",
    )
    _insert_project(
        database_path,
        workspace_id="workspace-b",
        project_id="project-a",
    )

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingProjectScopeError,
    ):
        store.create(_binding())


def test_duplicate_binding_id_maps_to_domain_error(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    binding_id = create_github_source_binding_id()

    first = _binding(
        repository_id="1001",
        binding_id=binding_id,
    )
    second = _binding(
        repository_id="1002",
        binding_id=binding_id,
    )

    store.create(first)

    with pytest.raises(
        GitHubSourceBindingAlreadyExistsError,
    ):
        store.create(second)


def test_duplicate_current_repository_maps_to_domain_error(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    store.create(
        _binding(repository_id="1001")
    )

    with pytest.raises(
        GitHubSourceBindingAlreadyExistsError,
    ):
        store.create(
            _binding(repository_id="1001")
        )


def test_load_missing_binding(
    database_path: Path,
):
    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingNotFoundError,
    ):
        store.load(
            create_github_source_binding_id()
        )


def test_load_current_repository_is_exact(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )
    binding = _binding(
        repository_id="1001"
    )

    store.create(binding)

    assert (
        store.load_current_by_repository_id(
            "1001"
        )
        == binding
    )

    with pytest.raises(
        GitHubSourceBindingNotFoundError,
    ):
        store.load_current_by_repository_id(
            " 1001 "
        )


def test_repository_lookup_does_not_coerce_types(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )
    store.create(
        _binding(repository_id="1001")
    )

    with pytest.raises(ValueError):
        store.load_current_by_repository_id(
            1001
        )


def test_multiple_repositories_can_bind_same_project(
    database_path: Path,
):
    _scope(database_path)

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    first = store.create(
        _binding(repository_id="1001")
    )
    second = store.create(
        _binding(repository_id="1002")
    )

    listed = store.list_project_bindings(
        workspace_id="workspace-a",
        project_id="project-a",
    )

    assert listed == [
        first,
        second,
    ]


def test_repository_history_preserves_period_order(
    database_path: Path,
):
    _scope(database_path)

    first = _binding(
        repository_id="1001",
        created_at=NOW,
    )
    second = _binding(
        repository_id="1001",
        created_at=NOW + timedelta(minutes=2),
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
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
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                first.github_source_binding_id,
                first.repository_id,
                first.workspace_id,
                first.project_id,
                first.installation_id,
                first.created_at.isoformat(),
            ),
        )

        connection.execute(
            "DROP TRIGGER "
            "prevent_github_source_binding_update"
        )

        connection.execute(
            """
            UPDATE github_source_bindings
            SET
                retired_at = ?,
                retired_reason = ?
            WHERE github_source_binding_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(minutes=1)
                ).isoformat(),
                "repository moved",
                first.github_source_binding_id,
            ),
        )

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
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                second.github_source_binding_id,
                second.repository_id,
                second.workspace_id,
                second.project_id,
                second.installation_id,
                second.created_at.isoformat(),
            ),
        )
    finally:
        connection.close()

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    history = store.list_repository_history(
        "1001"
    )

    assert [
        item.github_source_binding_id
        for item in history
    ] == [
        first.github_source_binding_id,
        second.github_source_binding_id,
    ]
    assert history[0].retired_at == (
        NOW + timedelta(minutes=1)
    )
    assert history[1].retired_at is None


def test_unknown_repository_history_is_empty(
    database_path: Path,
):
    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    assert store.list_repository_history(
        "9999"
    ) == []


def test_unknown_project_binding_list_is_empty(
    database_path: Path,
):
    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    assert store.list_project_bindings(
        workspace_id="workspace-a",
        project_id="project-a",
    ) == []


def test_unknown_integrity_error_is_not_misclassified(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _scope(database_path)

    import execution_evidence.sqlite_github_source_binding_store as module

    real_connect = (
        connect_execution_evidence_database
    )

    class FailingConnection:
        def __init__(
            self,
            connection: sqlite3.Connection,
        ) -> None:
            self._connection = connection

        @property
        def in_transaction(self):
            return self._connection.in_transaction

        def execute(
            self,
            sql,
            parameters=(),
        ):
            if (
                "INSERT INTO github_source_bindings"
                in sql
            ):
                raise sqlite3.IntegrityError(
                    "CHECK constraint failed: "
                    "unexpected_constraint"
                )

            return self._connection.execute(
                sql,
                parameters,
            )

        def close(self):
            self._connection.close()

    def connect_with_unknown_integrity_error(
        path,
    ):
        return FailingConnection(
            real_connect(path)
        )

    monkeypatch.setattr(
        module,
        "connect_execution_evidence_database",
        connect_with_unknown_integrity_error,
    )

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingStoreError,
    ) as raised:
        store.create(_binding())

    assert not isinstance(
        raised.value,
        GitHubSourceBindingAlreadyExistsError,
    )


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"

    store = SQLiteGitHubSourceBindingStore(
        database_path
    )

    with pytest.raises(
        GitHubSourceBindingStoreError,
    ):
        store.load_current_by_repository_id(
            "1001"
        )
