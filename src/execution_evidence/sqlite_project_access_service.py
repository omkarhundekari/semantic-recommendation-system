from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.project_access_service import (
    ProjectAccessNotFoundError,
    ProjectAccessService,
    ProjectAccessStoreError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLiteProjectAccessService(
    ProjectAccessService
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def authorize(
        self,
        *,
        principal: AuthenticatedRequestPrincipal,
        workspace_id: str,
        project_id: str,
    ) -> AuthorizedProjectContext:
        if not isinstance(
            principal,
            AuthenticatedRequestPrincipal,
        ):
            raise TypeError(
                "Project authorization requires an "
                "authenticated request principal."
            )

        self._validate_scope(
            workspace_id,
            name="Workspace ID",
        )
        self._validate_scope(
            project_id,
            name="Project ID",
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
                    principal.principal_id,
                    membership.membership_id,
                    membership.workspace_id,
                    project.project_id
                FROM principals AS principal
                JOIN workspace_memberships AS membership
                    ON
                        membership.principal_id =
                            principal.principal_id
                        AND membership.workspace_id = ?
                        AND membership.status = 'active'
                JOIN projects AS project
                    ON
                        project.workspace_id =
                            membership.workspace_id
                        AND project.project_id = ?
                WHERE
                    principal.principal_id = ?
                    AND principal.status = 'active'
                LIMIT 1
                """,
                (
                    workspace_id,
                    project_id,
                    principal.principal_id,
                ),
            ).fetchone()

            if row is None:
                raise ProjectAccessNotFoundError(
                    "Project does not exist."
                )

            return AuthorizedProjectContext(
                principal_id=row["principal_id"],
                membership_id=row["membership_id"],
                workspace_id=row["workspace_id"],
                project_id=row["project_id"],
            )

        except ProjectAccessNotFoundError:
            raise
        except sqlite3.Error as error:
            raise ProjectAccessStoreError(
                "Could not authorize project access."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _validate_scope(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be text."
            )

        if not value:
            raise ValueError(
                f"{name} must be non-empty."
            )

        if value != value.strip():
            raise ValueError(
                f"{name} must not contain surrounding "
                "whitespace."
            )
