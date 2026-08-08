from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.authorized_workspace_context import (
    AuthorizedWorkspaceContext,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.workspace_access_service import (
    WorkspaceAccessNotFoundError,
    WorkspaceAccessService,
    WorkspaceAccessStoreError,
)


class SQLiteWorkspaceAccessService(
    WorkspaceAccessService
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
    ) -> AuthorizedWorkspaceContext:
        if not isinstance(
            principal,
            AuthenticatedRequestPrincipal,
        ):
            raise TypeError(
                "Workspace authorization requires an "
                "authenticated request principal."
            )

        self._validate_scope(
            workspace_id,
            name="Workspace ID",
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
                    membership.role,
                    membership.workspace_id
                FROM principals AS principal
                JOIN workspace_memberships AS membership
                    ON
                        membership.principal_id =
                            principal.principal_id
                        AND membership.workspace_id = ?
                        AND membership.status = 'active'
                JOIN workspaces AS workspace
                    ON
                        workspace.workspace_id =
                            membership.workspace_id
                WHERE
                    principal.principal_id = ?
                    AND principal.status = 'active'
                LIMIT 1
                """,
                (
                    workspace_id,
                    principal.principal_id,
                ),
            ).fetchone()

            if row is None:
                raise WorkspaceAccessNotFoundError(
                    "Workspace does not exist."
                )

            return AuthorizedWorkspaceContext(
                principal_id=row["principal_id"],
                membership_id=row["membership_id"],
                membership_role=row["role"],
                workspace_id=row["workspace_id"],
            )

        except WorkspaceAccessNotFoundError:
            raise
        except sqlite3.Error as error:
            raise WorkspaceAccessStoreError(
                "Could not authorize workspace access."
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
