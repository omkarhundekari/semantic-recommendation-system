from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


WorkspaceDiscoveryRole = Literal[
    "owner",
    "admin",
    "member",
    "viewer",
]


MAX_WORKSPACE_DISCOVERY_RESULTS = 500


class WorkspaceDiscoveryError(RuntimeError):
    pass


class WorkspaceDiscoveryStoreError(
    WorkspaceDiscoveryError
):
    pass


class DiscoveredWorkspace(BaseModel):
    """One workspace currently accessible to a principal."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    workspace_id: str = Field(min_length=1)
    workspace_kind: Literal[
        "internal",
        "provisioned",
    ]
    membership_id: str = Field(min_length=1)
    membership_role: WorkspaceDiscoveryRole
    membership_revision: int = Field(ge=0)
    workspace_created_at: datetime
    workspace_updated_at: datetime
    membership_created_at: datetime
    membership_updated_at: datetime

    @field_validator(
        "workspace_created_at",
        "workspace_updated_at",
        "membership_created_at",
        "membership_updated_at",
    )
    @classmethod
    def require_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Workspace discovery timestamps "
                "must be timezone-aware."
            )

        return value


class WorkspaceDiscoveryResult(BaseModel):
    """Bounded principal-scoped workspace discovery result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    workspaces: List[DiscoveredWorkspace]
    truncated: bool



class SQLiteWorkspaceDiscoveryService:
    """Discover current workspaces visible to one principal.

    Discovery is principal-scoped and does not trust caller-
    supplied workspace identities.

    A workspace is discoverable only through an active
    membership with a currently assigned role and an active
    durable principal.

    Removed, suspended, and role-less memberships are excluded.

    Results are capped by a server-owned synchronous ceiling.
    Cursor pagination can extend discovery later without allowing
    an unbounded response to become part of the API contract.
    """

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def discover(
        self,
        *,
        principal: AuthenticatedRequestPrincipal,
    ) -> WorkspaceDiscoveryResult:
        if not isinstance(
            principal,
            AuthenticatedRequestPrincipal,
        ):
            raise TypeError(
                "Workspace discovery requires an "
                "authenticated request principal."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN")

            rows = connection.execute(
                """
                SELECT
                    workspace.workspace_id,
                    workspace.workspace_kind,
                    workspace.created_at
                        AS workspace_created_at,
                    workspace.updated_at
                        AS workspace_updated_at,
                    membership.membership_id,
                    membership.role
                        AS membership_role,
                    membership.revision
                        AS membership_revision,
                    membership.created_at
                        AS membership_created_at,
                    membership.updated_at
                        AS membership_updated_at
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
                ORDER BY
                    membership.updated_at DESC,
                    membership.workspace_id ASC
                LIMIT ?
                """,
                (
                    principal.principal_id,
                    (
                        MAX_WORKSPACE_DISCOVERY_RESULTS
                        + 1
                    ),
                ),
            ).fetchall()

            if connection.in_transaction:
                connection.rollback()

            truncated = (
                len(rows)
                > MAX_WORKSPACE_DISCOVERY_RESULTS
            )

            bounded_rows = rows[
                :MAX_WORKSPACE_DISCOVERY_RESULTS
            ]

            workspaces = [
                DiscoveredWorkspace(
                    workspace_id=row[
                        "workspace_id"
                    ],
                    workspace_kind=row[
                        "workspace_kind"
                    ],
                    membership_id=row[
                        "membership_id"
                    ],
                    membership_role=row[
                        "membership_role"
                    ],
                    membership_revision=int(
                        row[
                            "membership_revision"
                        ]
                    ),
                    workspace_created_at=row[
                        "workspace_created_at"
                    ],
                    workspace_updated_at=row[
                        "workspace_updated_at"
                    ],
                    membership_created_at=row[
                        "membership_created_at"
                    ],
                    membership_updated_at=row[
                        "membership_updated_at"
                    ],
                )
                for row in bounded_rows
            ]

            return WorkspaceDiscoveryResult(
                workspaces=workspaces,
                truncated=truncated,
            )

        except (
            TypeError,
            ValueError,
        ):
            if connection.in_transaction:
                connection.rollback()
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.rollback()

            raise WorkspaceDiscoveryStoreError(
                "Could not discover accessible "
                "workspaces."
            ) from error
        finally:
            connection.close()


    def list_accessible(
        self,
        *,
        principal: AuthenticatedRequestPrincipal,
    ) -> List[DiscoveredWorkspace]:
        """Return the bounded workspace list only.

        Call discover() when the caller also needs to know
        whether the server-owned discovery ceiling truncated
        additional accessible workspaces.
        """

        return self.discover(
            principal=principal
        ).workspaces
