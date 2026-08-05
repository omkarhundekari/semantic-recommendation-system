from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipRoleTransition,
    create_workspace_membership_role_transition_id,
)


BOOTSTRAP_BLOCKING_ROLES = (
    "owner",
    "admin",
)


class WorkspaceOwnerBootstrapError(RuntimeError):
    pass


class WorkspaceOwnerBootstrapNotFoundError(
    WorkspaceOwnerBootstrapError
):
    pass


class WorkspaceOwnerAlreadyBootstrappedError(
    WorkspaceOwnerBootstrapError
):
    pass


class WorkspaceOwnerBootstrapEligibilityError(
    WorkspaceOwnerBootstrapError
):
    pass


class WorkspaceOwnerBootstrapResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    membership: WorkspaceMembership
    transition: WorkspaceMembershipRoleTransition


class SQLiteWorkspaceOwnerBootstrapService:
    """Trusted, non-request-scoped first-owner bootstrap.

    This primitive operates only on an existing workspace
    and an existing active membership. Authority comes from
    outside the membership graph, so bootstrap transitions
    intentionally record no changed-by principal.
    """

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    def bootstrap_first_owner(
        self,
        *,
        workspace_id: str,
        membership_id: str,
        changed_at: datetime,
        reason: str | None = None,
    ) -> WorkspaceOwnerBootstrapResult:
        self._validate_identifier(
            workspace_id,
            name="Workspace ID",
        )
        self._validate_identifier(
            membership_id,
            name="Membership ID",
        )

        if (
            changed_at.tzinfo is None
            or changed_at.utcoffset() is None
        ):
            raise ValueError(
                "Workspace owner bootstrap timestamp "
                "must be timezone-aware."
            )

        normalized_reason = (
            reason.strip()
            if reason is not None
            and reason.strip()
            else None
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
                (workspace_id,),
            ).fetchone()

            if workspace is None:
                raise WorkspaceOwnerBootstrapNotFoundError(
                    "Workspace does not exist."
                )

            existing_manager = connection.execute(
                """
                SELECT
                    membership_id,
                    role
                FROM workspace_memberships
                WHERE
                    workspace_id = ?
                    AND status = 'active'
                    AND role IN ('owner', 'admin')
                LIMIT 1
                """,
                (workspace_id,),
            ).fetchone()

            if existing_manager is not None:
                raise (
                    WorkspaceOwnerAlreadyBootstrappedError(
                        "Workspace already has an active "
                        "owner or admin membership."
                    )
                )

            row = connection.execute(
                """
                SELECT
                    membership.membership_row_id,
                    membership.membership_id,
                    membership.workspace_id,
                    membership.principal_id,
                    membership.status,
                    membership.role,
                    membership.revision,
                    membership.created_by_principal_id,
                    membership.created_at,
                    membership.updated_at,
                    membership.status_changed_at,
                    principal.status AS principal_status
                FROM workspace_memberships AS membership
                JOIN principals AS principal
                    ON principal.principal_id =
                        membership.principal_id
                WHERE
                    membership.workspace_id = ?
                    AND membership.membership_id = ?
                """,
                (
                    workspace_id,
                    membership_id,
                ),
            ).fetchone()

            if row is None:
                raise WorkspaceOwnerBootstrapNotFoundError(
                    "Workspace membership does not exist."
                )

            if row["principal_status"] != "active":
                raise WorkspaceOwnerBootstrapEligibilityError(
                    "Bootstrap principal must be active."
                )

            if row["status"] != "active":
                raise WorkspaceOwnerBootstrapEligibilityError(
                    "Bootstrap membership must be active."
                )

            if row["role"] is not None:
                raise WorkspaceOwnerBootstrapEligibilityError(
                    "Bootstrap membership must have no "
                    "assigned role."
                )

            current_revision = int(
                row["revision"]
            )
            next_revision = (
                current_revision + 1
            )

            transition = (
                WorkspaceMembershipRoleTransition(
                    transition_id=(
                        create_workspace_membership_role_transition_id()
                    ),
                    membership_id=str(
                        row["membership_id"]
                    ),
                    workspace_id=str(
                        row["workspace_id"]
                    ),
                    principal_id=str(
                        row["principal_id"]
                    ),
                    previous_role=None,
                    new_role="owner",
                    previous_revision=(
                        current_revision
                    ),
                    resulting_revision=(
                        next_revision
                    ),
                    changed_at=changed_at,
                    changed_by_principal_id=None,
                    reason=normalized_reason,
                )
            )

            connection.execute(
                """
                INSERT INTO
                    workspace_membership_role_transitions (
                        role_transition_id,
                        membership_row_id,
                        membership_id,
                        workspace_id,
                        principal_id,
                        previous_role,
                        new_role,
                        previous_revision,
                        resulting_revision,
                        changed_at,
                        changed_by_principal_id,
                        reason
                    )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    transition.transition_id,
                    int(
                        row["membership_row_id"]
                    ),
                    transition.membership_id,
                    transition.workspace_id,
                    transition.principal_id,
                    transition.previous_role,
                    transition.new_role,
                    transition.previous_revision,
                    transition.resulting_revision,
                    transition.changed_at.isoformat(),
                    transition.changed_by_principal_id,
                    transition.reason,
                ),
            )

            stored_row = connection.execute(
                """
                SELECT
                    membership_id,
                    workspace_id,
                    principal_id,
                    status,
                    role,
                    revision,
                    created_by_principal_id,
                    created_at,
                    updated_at,
                    status_changed_at
                FROM workspace_memberships
                WHERE
                    workspace_id = ?
                    AND membership_id = ?
                """,
                (
                    workspace_id,
                    membership_id,
                ),
            ).fetchone()

            if stored_row is None:
                raise WorkspaceOwnerBootstrapError(
                    "Bootstrapped membership disappeared "
                    "before commit."
                )

            stored = WorkspaceMembership(
                membership_id=stored_row[
                    "membership_id"
                ],
                workspace_id=stored_row[
                    "workspace_id"
                ],
                principal_id=stored_row[
                    "principal_id"
                ],
                status=stored_row["status"],
                role=stored_row["role"],
                revision=int(
                    stored_row["revision"]
                ),
                created_by_principal_id=stored_row[
                    "created_by_principal_id"
                ],
                created_at=stored_row[
                    "created_at"
                ],
                updated_at=stored_row[
                    "updated_at"
                ],
                status_changed_at=stored_row[
                    "status_changed_at"
                ],
            )

            if (
                stored.status != "active"
                or stored.role != "owner"
                or stored.revision
                != next_revision
                or stored.updated_at
                != changed_at
            ):
                raise WorkspaceOwnerBootstrapError(
                    "Workspace owner bootstrap did not "
                    "produce authoritative current state."
                )

            connection.execute("COMMIT")

            return WorkspaceOwnerBootstrapResult(
                membership=stored,
                transition=transition,
            )

        except WorkspaceOwnerBootstrapError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise WorkspaceOwnerBootstrapEligibilityError(
                "Workspace owner bootstrap constraint "
                "conflict."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise WorkspaceOwnerBootstrapError(
                "Could not bootstrap workspace owner."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
        if not isinstance(value, str):
            raise TypeError(
                f"{name} must be a string."
            )

        if not value:
            raise ValueError(
                f"{name} must be non-empty."
            )

        if value != value.strip():
            raise ValueError(
                f"{name} must not contain "
                "surrounding whitespace."
            )

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
