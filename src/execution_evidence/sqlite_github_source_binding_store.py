from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from execution_evidence.github_source_binding import (
    GitHubSourceBinding,
)
from execution_evidence.github_source_binding_store import (
    GitHubSourceBindingAlreadyExistsError,
    GitHubSourceBindingNotFoundError,
    GitHubSourceBindingProjectNotFoundError,
    GitHubSourceBindingProjectScopeError,
    GitHubSourceBindingStore,
    GitHubSourceBindingStoreError,
    GitHubSourceBindingTransitionError,
    GitHubSourceBindingWorkspaceNotFoundError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLiteGitHubSourceBindingStore(
    GitHubSourceBindingStore
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def create(
        self,
        binding: GitHubSourceBinding,
    ) -> GitHubSourceBinding:
        if (
            binding.retired_at is not None
            or binding.retired_reason is not None
        ):
            raise GitHubSourceBindingTransitionError(
                "New GitHub source bindings must "
                "begin current."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            workspace = connection.execute(
                """
                SELECT workspace_id
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (binding.workspace_id,),
            ).fetchone()

            if workspace is None:
                raise (
                    GitHubSourceBindingWorkspaceNotFoundError(
                        "GitHub source binding workspace "
                        "does not exist."
                    )
                )

            scoped_project = connection.execute(
                """
                SELECT project_row_id
                FROM projects
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                """,
                (
                    binding.workspace_id,
                    binding.project_id,
                ),
            ).fetchone()

            if scoped_project is None:
                project_elsewhere = connection.execute(
                    """
                    SELECT workspace_id
                    FROM projects
                    WHERE project_id = ?
                    LIMIT 1
                    """,
                    (binding.project_id,),
                ).fetchone()

                if project_elsewhere is not None:
                    raise GitHubSourceBindingProjectScopeError(
                        "GitHub source binding project "
                        "belongs to a different workspace."
                    )

                raise GitHubSourceBindingProjectNotFoundError(
                    "GitHub source binding project "
                    "does not exist."
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
                VALUES (
                    ?, ?, ?, ?, ?, ?, NULL, NULL
                )
                """,
                (
                    binding.github_source_binding_id,
                    binding.repository_id,
                    binding.workspace_id,
                    binding.project_id,
                    binding.installation_id,
                    binding.created_at.isoformat(),
                ),
            )

            stored = self._load_from_connection(
                connection,
                binding.github_source_binding_id,
            )

            if stored != binding:
                raise GitHubSourceBindingStoreError(
                    "Stored GitHub source binding does "
                    "not match authoritative state."
                )

            connection.execute("COMMIT")
            return stored

        except (
            GitHubSourceBindingStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            self._raise_create_integrity_error(error)
        except sqlite3.Error as error:
            self._rollback(connection)
            raise GitHubSourceBindingStoreError(
                "Could not create GitHub source binding."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        github_source_binding_id: str,
    ) -> GitHubSourceBinding:
        self._validate_identifier(
            github_source_binding_id,
            name="GitHub source binding ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_from_connection(
                connection,
                github_source_binding_id,
            )
        except GitHubSourceBindingNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubSourceBindingStoreError(
                "Could not load GitHub source binding."
            ) from error
        finally:
            connection.close()

    def load_current_by_repository_id(
        self,
        repository_id: str,
    ) -> GitHubSourceBinding:
        self._validate_lookup_value(
            repository_id,
            name="GitHub repository ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            row = connection.execute(
                """
                SELECT
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_source_bindings
                WHERE
                    repository_id = ?
                    AND retired_at IS NULL
                """,
                (repository_id,),
            ).fetchone()

            if row is None:
                raise GitHubSourceBindingNotFoundError(
                    "Current GitHub source binding "
                    "does not exist."
                )

            return self._binding_from_row(row)

        except GitHubSourceBindingNotFoundError:
            raise
        except sqlite3.Error as error:
            raise GitHubSourceBindingStoreError(
                "Could not load current GitHub source "
                "binding."
            ) from error
        finally:
            connection.close()

    def list_repository_history(
        self,
        repository_id: str,
    ) -> List[GitHubSourceBinding]:
        self._validate_lookup_value(
            repository_id,
            name="GitHub repository ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            rows = connection.execute(
                """
                SELECT
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_source_bindings
                WHERE repository_id = ?
                ORDER BY
                    created_at ASC,
                    github_source_binding_row_id ASC
                """,
                (repository_id,),
            ).fetchall()

            return [
                self._binding_from_row(row)
                for row in rows
            ]

        except sqlite3.Error as error:
            raise GitHubSourceBindingStoreError(
                "Could not list GitHub source binding "
                "history."
            ) from error
        finally:
            connection.close()

    def list_project_bindings(
        self,
        *,
        workspace_id: str,
        project_id: str,
    ) -> List[GitHubSourceBinding]:
        self._validate_identifier(
            workspace_id,
            name="Workspace ID",
        )
        self._validate_identifier(
            project_id,
            name="Project ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            rows = connection.execute(
                """
                SELECT
                    github_source_binding_id,
                    repository_id,
                    workspace_id,
                    project_id,
                    installation_id,
                    created_at,
                    retired_at,
                    retired_reason
                FROM github_source_bindings
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                ORDER BY
                    created_at ASC,
                    github_source_binding_row_id ASC
                """,
                (
                    workspace_id,
                    project_id,
                ),
            ).fetchall()

            return [
                self._binding_from_row(row)
                for row in rows
            ]

        except sqlite3.Error as error:
            raise GitHubSourceBindingStoreError(
                "Could not list project GitHub source "
                "bindings."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_from_connection(
        connection: sqlite3.Connection,
        github_source_binding_id: str,
    ) -> GitHubSourceBinding:
        row = connection.execute(
            """
            SELECT
                github_source_binding_id,
                repository_id,
                workspace_id,
                project_id,
                installation_id,
                created_at,
                retired_at,
                retired_reason
            FROM github_source_bindings
            WHERE github_source_binding_id = ?
            """,
            (github_source_binding_id,),
        ).fetchone()

        if row is None:
            raise GitHubSourceBindingNotFoundError(
                "GitHub source binding does not exist."
            )

        return (
            SQLiteGitHubSourceBindingStore
            ._binding_from_row(row)
        )

    @staticmethod
    def _binding_from_row(
        row: sqlite3.Row,
    ) -> GitHubSourceBinding:
        return GitHubSourceBinding(
            github_source_binding_id=row[
                "github_source_binding_id"
            ],
            repository_id=row["repository_id"],
            workspace_id=row["workspace_id"],
            project_id=row["project_id"],
            installation_id=row["installation_id"],
            created_at=row["created_at"],
            retired_at=row["retired_at"],
            retired_reason=row["retired_reason"],
        )

    @staticmethod
    def _raise_create_integrity_error(
        error: sqlite3.IntegrityError,
    ) -> None:
        message = str(error)

        if (
            "UNIQUE constraint failed: "
            "github_source_bindings."
            "github_source_binding_id"
            in message
        ):
            raise GitHubSourceBindingAlreadyExistsError(
                "GitHub source binding ID already "
                "exists."
            ) from error

        if (
            "UNIQUE constraint failed: "
            "github_source_bindings.repository_id"
            in message
        ):
            raise GitHubSourceBindingAlreadyExistsError(
                "GitHub repository already has a "
                "current source binding."
            ) from error

        raise GitHubSourceBindingStoreError(
            "Could not create GitHub source binding."
        ) from error

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{name} must be non-empty text."
            )

        if value != value.strip():
            raise ValueError(
                f"{name} must not contain "
                "surrounding whitespace."
            )

    @staticmethod
    def _validate_lookup_value(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"{name} must be non-empty text."
            )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
