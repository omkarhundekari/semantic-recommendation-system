from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.workspace import (
    ProvisionedWorkspace,
    create_workspace_id,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipRoleTransition,
    create_workspace_membership_id,
    create_workspace_membership_role_transition_id,
)


class WorkspaceProvisioningError(RuntimeError):
    pass


class WorkspaceProvisioningPrincipalUnavailableError(
    WorkspaceProvisioningError
):
    """Provisioning principal is absent or inactive."""

    pass


class WorkspaceProvisioningIdentityCollisionError(
    WorkspaceProvisioningError
):
    """A generated opaque provisioning identity collided."""

    pass


class WorkspaceProvisioningStateError(
    WorkspaceProvisioningError
):
    """Committed graph would violate provisioning invariants."""

    pass


class WorkspaceProvisioningResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    workspace: ProvisionedWorkspace
    membership: WorkspaceMembership
    owner_transition: WorkspaceMembershipRoleTransition


class SQLiteWorkspaceProvisioningService:
    """Atomically create a provisioned workspace and first owner.

    This is a trusted provisioning primitive, not a request-scoped
    authorization service.

    Workspace creation, membership genesis, and initial owner role
    assignment intentionally share one BEGIN IMMEDIATE transaction.

    Membership insertion relies on the authoritative SQLite genesis
    trigger. Owner assignment relies on the authoritative membership
    role-transition trigger rather than directly mutating role state.
    """

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def provision(
        self,
        *,
        principal_id: str,
        created_at: datetime,
        reason: Optional[str] = None,
    ) -> WorkspaceProvisioningResult:
        self._validate_identifier(
            principal_id,
            name="Principal ID",
        )

        if (
            created_at.tzinfo is None
            or created_at.utcoffset() is None
        ):
            raise ValueError(
                "Workspace provisioning timestamp "
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

            principal = connection.execute(
                """
                SELECT
                    principal_id,
                    status
                FROM principals
                WHERE principal_id = ?
                """,
                (principal_id,),
            ).fetchone()

            if (
                principal is None
                or principal["status"] != "active"
            ):
                raise (
                    WorkspaceProvisioningPrincipalUnavailableError(
                        "Provisioning principal does not "
                        "exist or is not active."
                    )
                )

            workspace_id = create_workspace_id()
            membership_id = (
                create_workspace_membership_id()
            )
            owner_transition_id = (
                create_workspace_membership_role_transition_id()
            )

            self._require_generated_identity_available(
                connection,
                table="workspaces",
                column="workspace_id",
                value=workspace_id,
                identity_name="workspace",
            )
            self._require_generated_identity_available(
                connection,
                table="workspace_memberships",
                column="membership_id",
                value=membership_id,
                identity_name="workspace membership",
            )
            self._require_generated_identity_available(
                connection,
                table=(
                    "workspace_membership_role_transitions"
                ),
                column="role_transition_id",
                value=owner_transition_id,
                identity_name=(
                    "workspace membership role transition"
                ),
            )

            workspace = ProvisionedWorkspace(
                workspace_id=workspace_id,
                created_at=created_at,
                updated_at=created_at,
            )

            membership = WorkspaceMembership(
                membership_id=membership_id,
                workspace_id=workspace.workspace_id,
                principal_id=principal_id,
                status="active",
                role=None,
                revision=0,
                created_by_principal_id=principal_id,
                created_at=created_at,
                updated_at=created_at,
                status_changed_at=created_at,
            )

            connection.execute(
                """
                INSERT INTO workspaces (
                    workspace_id,
                    created_at,
                    updated_at,
                    workspace_kind
                )
                VALUES (?, ?, ?, 'provisioned')
                """,
                (
                    workspace.workspace_id,
                    workspace.created_at.isoformat(),
                    workspace.updated_at.isoformat(),
                ),
            )

            connection.execute(
                """
                INSERT INTO workspace_memberships (
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
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    membership.membership_id,
                    membership.workspace_id,
                    membership.principal_id,
                    membership.status,
                    membership.role,
                    membership.revision,
                    membership.created_by_principal_id,
                    membership.created_at.isoformat(),
                    membership.updated_at.isoformat(),
                    (
                        membership
                        .status_changed_at
                        .isoformat()
                    ),
                ),
            )

            membership_row = connection.execute(
                """
                SELECT
                    membership_row_id,
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
                    workspace.workspace_id,
                    membership.membership_id,
                ),
            ).fetchone()

            if membership_row is None:
                raise WorkspaceProvisioningStateError(
                    "Provisioned workspace membership "
                    "disappeared before owner assignment."
                )

            owner_transition = (
                WorkspaceMembershipRoleTransition(
                    transition_id=owner_transition_id,
                    membership_id=membership.membership_id,
                    workspace_id=workspace.workspace_id,
                    principal_id=principal_id,
                    previous_role=None,
                    new_role="owner",
                    previous_revision=0,
                    resulting_revision=1,
                    changed_at=created_at,
                    changed_by_principal_id=None,
                    reason=normalized_reason,
                )
            )

            # Intentionally parallel with first-owner bootstrap:
            # this transition is written directly so its existing
            # database trigger remains the sole authority that
            # changes workspace_memberships.role and revision.
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
                    owner_transition.transition_id,
                    int(
                        membership_row[
                            "membership_row_id"
                        ]
                    ),
                    owner_transition.membership_id,
                    owner_transition.workspace_id,
                    owner_transition.principal_id,
                    owner_transition.previous_role,
                    owner_transition.new_role,
                    owner_transition.previous_revision,
                    owner_transition.resulting_revision,
                    owner_transition.changed_at.isoformat(),
                    (
                        owner_transition
                        .changed_by_principal_id
                    ),
                    owner_transition.reason,
                ),
            )

            stored_workspace_row = connection.execute(
                """
                SELECT
                    workspace_id,
                    workspace_kind,
                    created_at,
                    updated_at
                FROM workspaces
                WHERE workspace_id = ?
                """,
                (workspace.workspace_id,),
            ).fetchone()

            stored_membership_row = connection.execute(
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
                    workspace.workspace_id,
                    membership.membership_id,
                ),
            ).fetchone()

            genesis_row = connection.execute(
                """
                SELECT
                    previous_status,
                    new_status,
                    previous_revision,
                    resulting_revision,
                    changed_at
                FROM workspace_membership_status_transitions
                WHERE
                    membership_id = ?
                    AND workspace_id = ?
                    AND resulting_revision = 0
                """,
                (
                    membership.membership_id,
                    workspace.workspace_id,
                ),
            ).fetchone()

            stored_owner_transition = connection.execute(
                """
                SELECT
                    role_transition_id,
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
                FROM workspace_membership_role_transitions
                WHERE role_transition_id = ?
                """,
                (owner_transition.transition_id,),
            ).fetchone()

            if (
                stored_workspace_row is None
                or stored_membership_row is None
                or genesis_row is None
                or stored_owner_transition is None
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace provisioning graph could "
                    "not be verified before commit."
                )

            stored_workspace = ProvisionedWorkspace(
                workspace_id=stored_workspace_row[
                    "workspace_id"
                ],
                workspace_kind=stored_workspace_row[
                    "workspace_kind"
                ],
                created_at=stored_workspace_row[
                    "created_at"
                ],
                updated_at=stored_workspace_row[
                    "updated_at"
                ],
            )

            stored_membership = WorkspaceMembership(
                membership_id=stored_membership_row[
                    "membership_id"
                ],
                workspace_id=stored_membership_row[
                    "workspace_id"
                ],
                principal_id=stored_membership_row[
                    "principal_id"
                ],
                status=stored_membership_row["status"],
                role=stored_membership_row["role"],
                revision=int(
                    stored_membership_row["revision"]
                ),
                created_by_principal_id=(
                    stored_membership_row[
                        "created_by_principal_id"
                    ]
                ),
                created_at=stored_membership_row[
                    "created_at"
                ],
                updated_at=stored_membership_row[
                    "updated_at"
                ],
                status_changed_at=stored_membership_row[
                    "status_changed_at"
                ],
            )

            if (
                stored_workspace.workspace_kind
                != "provisioned"
                or stored_workspace.workspace_id
                != workspace.workspace_id
                or stored_workspace.created_at
                != created_at
                or stored_workspace.updated_at
                != created_at
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace provisioning did not "
                    "produce authoritative workspace state."
                )

            if (
                stored_membership.workspace_id
                != stored_workspace.workspace_id
                or stored_membership.principal_id
                != principal_id
                or stored_membership.status != "active"
                or stored_membership.role != "owner"
                or stored_membership.revision != 1
                or (
                    stored_membership
                    .created_by_principal_id
                    != principal_id
                )
                or stored_membership.created_at
                != created_at
                or stored_membership.updated_at
                != created_at
                or stored_membership.status_changed_at
                != created_at
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace provisioning did not "
                    "produce authoritative owner "
                    "membership state."
                )

            if (
                genesis_row["previous_status"] is not None
                or genesis_row["new_status"] != "active"
                or genesis_row[
                    "previous_revision"
                ] is not None
                or int(
                    genesis_row[
                        "resulting_revision"
                    ]
                )
                != 0
                or genesis_row["changed_at"]
                != created_at.isoformat()
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace membership genesis "
                    "transition is invalid."
                )

            if (
                stored_owner_transition[
                    "role_transition_id"
                ]
                != owner_transition.transition_id
                or stored_owner_transition[
                    "membership_id"
                ]
                != owner_transition.membership_id
                or stored_owner_transition[
                    "workspace_id"
                ]
                != owner_transition.workspace_id
                or stored_owner_transition[
                    "principal_id"
                ]
                != owner_transition.principal_id
                or stored_owner_transition[
                    "previous_role"
                ]
                is not None
                or stored_owner_transition[
                    "new_role"
                ]
                != "owner"
                or int(
                    stored_owner_transition[
                        "previous_revision"
                    ]
                )
                != 0
                or int(
                    stored_owner_transition[
                        "resulting_revision"
                    ]
                )
                != 1
                or stored_owner_transition[
                    "changed_at"
                ]
                != owner_transition.changed_at.isoformat()
                or stored_owner_transition[
                    "changed_by_principal_id"
                ]
                is not None
                or stored_owner_transition[
                    "reason"
                ]
                != owner_transition.reason
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace owner transition is "
                    "not authoritative."
                )

            connection.execute("COMMIT")

            return WorkspaceProvisioningResult(
                workspace=stored_workspace,
                membership=stored_membership,
                owner_transition=owner_transition,
            )

        except WorkspaceProvisioningError:
            self._rollback(connection)
            raise
        except ValueError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise WorkspaceProvisioningStateError(
                "Workspace provisioning violated a "
                "storage integrity constraint."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise WorkspaceProvisioningError(
                "Could not provision workspace."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _require_generated_identity_available(
        connection: sqlite3.Connection,
        *,
        table: str,
        column: str,
        value: str,
        identity_name: str,
    ) -> None:
        allowed = {
            (
                "workspaces",
                "workspace_id",
            ),
            (
                "workspace_memberships",
                "membership_id",
            ),
            (
                "workspace_membership_role_transitions",
                "role_transition_id",
            ),
        }

        if (table, column) not in allowed:
            raise ValueError(
                "Unsupported provisioning identity "
                "collision check."
            )

        row = connection.execute(
            f"""
            SELECT 1
            FROM {table}
            WHERE {column} = ?
            LIMIT 1
            """,
            (value,),
        ).fetchone()

        if row is not None:
            raise WorkspaceProvisioningIdentityCollisionError(
                "Generated "
                f"{identity_name} identity collided "
                "with existing storage."
            )

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
