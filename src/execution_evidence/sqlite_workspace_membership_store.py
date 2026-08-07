from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, Optional

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.workspace_membership import (
    WorkspaceMembership,
    WorkspaceMembershipMutationResult,
    WorkspaceMembershipStatus,
    WorkspaceMembershipTransition,
    create_workspace_membership_transition_id,
)
from execution_evidence.workspace_membership_store import (
    WorkspaceMembershipAlreadyExistsError,
    WorkspaceMembershipInactiveError,
    WorkspaceMembershipNotFoundError,
    WorkspaceMembershipPrincipalNotFoundError,
    WorkspaceMembershipRevisionConflictError,
    WorkspaceMembershipStore,
    WorkspaceMembershipStoreError,
    WorkspaceMembershipTransitionError,
    WorkspaceNotFoundError,
)


class SQLiteWorkspaceMembershipStore(
    WorkspaceMembershipStore
):
    def __init__(
        self,
        path: Path | str,
        *,
        workspace_id: str,
    ) -> None:
        if not workspace_id:
            raise ValueError(
                "Workspace ID must be non-empty."
            )

        if workspace_id != workspace_id.strip():
            raise ValueError(
                "Workspace ID must not contain "
                "surrounding whitespace."
            )

        self._path = Path(path)
        self._workspace_id = workspace_id

    @property
    def path(self) -> Path:
        return self._path

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def create(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        if membership.workspace_id != self._workspace_id:
            raise WorkspaceMembershipStoreError(
                "Workspace membership does not belong "
                "to this store workspace."
            )

        if membership.status != "active":
            raise WorkspaceMembershipTransitionError(
                "New workspace memberships must begin "
                "active."
            )

        if membership.role is not None:
            raise WorkspaceMembershipTransitionError(
                "New workspace memberships must begin "
                "without an assigned role."
            )

        if membership.revision != 0:
            raise WorkspaceMembershipTransitionError(
                "New workspace memberships must begin "
                "at revision zero."
            )

        if (
            membership.updated_at
            != membership.created_at
            or membership.status_changed_at
            != membership.created_at
        ):
            raise WorkspaceMembershipTransitionError(
                "New workspace membership timestamps "
                "must begin at created_at."
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
                (self._workspace_id,),
            ).fetchone()

            if workspace is None:
                raise WorkspaceNotFoundError(
                    "Workspace does not exist."
                )

            principal = connection.execute(
                """
                SELECT principal_id
                FROM principals
                WHERE principal_id = ?
                """,
                (membership.principal_id,),
            ).fetchone()

            if principal is None:
                raise (
                    WorkspaceMembershipPrincipalNotFoundError(
                        "Principal does not exist."
                    )
                )

            if (
                membership.created_by_principal_id
                is not None
            ):
                creator = connection.execute(
                    """
                    SELECT principal_id
                    FROM principals
                    WHERE principal_id = ?
                    """,
                    (
                        membership
                        .created_by_principal_id,
                    ),
                ).fetchone()

                if creator is None:
                    raise (
                        WorkspaceMembershipPrincipalNotFoundError(
                            "Creating principal does "
                            "not exist."
                        )
                    )

            current = connection.execute(
                """
                SELECT membership_id
                FROM workspace_memberships
                WHERE
                    workspace_id = ?
                    AND principal_id = ?
                    AND status != 'removed'
                """,
                (
                    self._workspace_id,
                    membership.principal_id,
                ),
            ).fetchone()

            if current is not None:
                raise (
                    WorkspaceMembershipAlreadyExistsError(
                        "Current workspace membership "
                        "already exists."
                    )
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

            stored = self._load_by_id_from_connection(
                connection,
                membership.membership_id,
            )

            connection.execute("COMMIT")
            return stored

        except (
            WorkspaceMembershipStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)

            message = str(error)

            duplicate_current_membership = (
                "UNIQUE constraint failed: "
                "workspace_memberships.workspace_id, "
                "workspace_memberships.principal_id"
                in message
            )

            if duplicate_current_membership:
                raise (
                    WorkspaceMembershipAlreadyExistsError(
                        "Current workspace membership "
                        "already exists."
                    )
                ) from error

            raise WorkspaceMembershipStoreError(
                "Could not create workspace membership."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise WorkspaceMembershipStoreError(
                "Could not create workspace membership."
            ) from error
        finally:
            connection.close()

    def load_by_id(
        self,
        membership_id: str,
    ) -> WorkspaceMembership:
        self._validate_identifier(
            membership_id,
            name="Membership ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_by_id_from_connection(
                connection,
                membership_id,
            )
        except WorkspaceMembershipNotFoundError:
            raise
        except sqlite3.Error as error:
            raise WorkspaceMembershipStoreError(
                "Could not load workspace membership."
            ) from error
        finally:
            connection.close()

    def load_current(
        self,
        principal_id: str,
    ) -> WorkspaceMembership:
        self._validate_identifier(
            principal_id,
            name="Principal ID",
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
                    AND principal_id = ?
                    AND status != 'removed'
                """,
                (
                    self._workspace_id,
                    principal_id,
                ),
            ).fetchone()

            if row is None:
                raise WorkspaceMembershipNotFoundError(
                    "Current workspace membership "
                    "does not exist."
                )

            return self._membership_from_row(row)

        except WorkspaceMembershipNotFoundError:
            raise
        except sqlite3.Error as error:
            raise WorkspaceMembershipStoreError(
                "Could not load current workspace "
                "membership."
            ) from error
        finally:
            connection.close()

    def require_active(
        self,
        principal_id: str,
    ) -> WorkspaceMembership:
        membership = self.load_current(
            principal_id
        )

        if membership.status != "active":
            raise WorkspaceMembershipInactiveError(
                "Workspace membership is not active."
            )

        return membership

    def transition_status(
        self,
        membership_id: str,
        *,
        new_status: WorkspaceMembershipStatus,
        changed_at,
        expected_revision: int,
        reason: Optional[str] = None,
        changed_by_principal_id: Optional[str] = None,
    ) -> WorkspaceMembershipMutationResult:
        self._validate_identifier(
            membership_id,
            name="Membership ID",
        )

        if expected_revision < 0:
            raise ValueError(
                "Expected revision must be "
                "non-negative."
            )

        if (
            changed_at.tzinfo is None
            or changed_at.utcoffset() is None
        ):
            raise ValueError(
                "Membership transition timestamp "
                "must be timezone-aware."
            )

        normalized_reason = (
            reason.strip()
            if reason is not None
            and reason.strip()
            else None
        )

        if changed_by_principal_id is not None:
            if not changed_by_principal_id:
                raise ValueError(
                    "Membership transition actor must "
                    "be non-empty."
                )

            if (
                changed_by_principal_id
                != changed_by_principal_id.strip()
            ):
                raise ValueError(
                    "Membership transition actor must "
                    "not contain surrounding whitespace."
                )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            row = connection.execute(
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
                    self._workspace_id,
                    membership_id,
                ),
            ).fetchone()

            if row is None:
                raise WorkspaceMembershipNotFoundError(
                    "Workspace membership does not "
                    "exist."
                )

            previous_status = str(
                row["status"]
            )
            current_revision = int(
                row["revision"]
            )

            if expected_revision != current_revision:
                raise (
                    WorkspaceMembershipRevisionConflictError(
                        "Workspace membership revision "
                        "conflict: "
                        f"expected {expected_revision}, "
                        f"found {current_revision}."
                    )
                )

            if previous_status == new_status:
                raise (
                    WorkspaceMembershipTransitionError(
                        "Workspace membership "
                        "self-transitions are not allowed."
                    )
                )

            allowed = {
                "active": {
                    "suspended",
                    "removed",
                },
                "suspended": {
                    "active",
                    "removed",
                },
                "removed": set(),
            }

            if new_status not in allowed[
                previous_status
            ]:
                raise (
                    WorkspaceMembershipTransitionError(
                        "Workspace membership status "
                        "transition is not allowed: "
                        f"{previous_status} -> "
                        f"{new_status}."
                    )
                )

            next_revision = current_revision + 1

            transition = WorkspaceMembershipTransition(
                transition_id=(
                    create_workspace_membership_transition_id()
                ),
                membership_id=membership_id,
                workspace_id=self._workspace_id,
                principal_id=str(
                    row["principal_id"]
                ),
                previous_status=previous_status,
                new_status=new_status,
                previous_revision=current_revision,
                resulting_revision=next_revision,
                changed_at=changed_at,
                changed_by_principal_id=(
                    changed_by_principal_id
                ),
                reason=normalized_reason,
            )

            connection.execute(
                """
                INSERT INTO
                    workspace_membership_status_transitions (
                        transition_id,
                        membership_row_id,
                        membership_id,
                        workspace_id,
                        principal_id,
                        previous_status,
                        new_status,
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
                    transition.previous_status,
                    transition.new_status,
                    transition.previous_revision,
                    transition.resulting_revision,
                    transition.changed_at.isoformat(),
                    transition.changed_by_principal_id,
                    transition.reason,
                ),
            )

            stored = self._load_by_id_from_connection(
                connection,
                membership_id,
            )

            if (
                stored.status != new_status
                or stored.revision
                != next_revision
                or stored.status_changed_at
                != changed_at
            ):
                raise WorkspaceMembershipStoreError(
                    "Workspace membership transition "
                    "did not produce authoritative "
                    "current state."
                )

            connection.execute("COMMIT")

            return WorkspaceMembershipMutationResult(
                membership=stored,
                transition=transition,
            )

        except (
            WorkspaceMembershipStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise WorkspaceMembershipTransitionError(
                "Workspace membership transition "
                "constraint conflict."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise WorkspaceMembershipStoreError(
                "Could not transition workspace "
                "membership status."
            ) from error
        finally:
            connection.close()

    def list_transitions(
        self,
        membership_id: str,
    ) -> List[WorkspaceMembershipTransition]:
        self._validate_identifier(
            membership_id,
            name="Membership ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            membership = connection.execute(
                """
                SELECT membership_row_id
                FROM workspace_memberships
                WHERE
                    workspace_id = ?
                    AND membership_id = ?
                """,
                (
                    self._workspace_id,
                    membership_id,
                ),
            ).fetchone()

            if membership is None:
                raise WorkspaceMembershipNotFoundError(
                    "Workspace membership does not "
                    "exist."
                )

            rows = connection.execute(
                """
                SELECT
                    transition_id,
                    membership_id,
                    workspace_id,
                    principal_id,
                    previous_status,
                    new_status,
                    previous_revision,
                    resulting_revision,
                    changed_at,
                    changed_by_principal_id,
                    reason
                FROM workspace_membership_status_transitions
                WHERE membership_row_id = ?
                ORDER BY resulting_revision ASC
                """,
                (
                    int(
                        membership[
                            "membership_row_id"
                        ]
                    ),
                ),
            ).fetchall()

            return [
                WorkspaceMembershipTransition(
                    transition_id=row[
                        "transition_id"
                    ],
                    membership_id=row[
                        "membership_id"
                    ],
                    workspace_id=row[
                        "workspace_id"
                    ],
                    principal_id=row[
                        "principal_id"
                    ],
                    previous_status=row[
                        "previous_status"
                    ],
                    new_status=row[
                        "new_status"
                    ],
                    previous_revision=row[
                        "previous_revision"
                    ],
                    resulting_revision=int(
                        row[
                            "resulting_revision"
                        ]
                    ),
                    changed_at=row[
                        "changed_at"
                    ],
                    changed_by_principal_id=row[
                        "changed_by_principal_id"
                    ],
                    reason=row["reason"],
                )
                for row in rows
            ]

        except WorkspaceMembershipNotFoundError:
            raise
        except sqlite3.Error as error:
            raise WorkspaceMembershipStoreError(
                "Could not list workspace membership "
                "transitions."
            ) from error
        finally:
            connection.close()

    def _load_by_id_from_connection(
        self,
        connection: sqlite3.Connection,
        membership_id: str,
    ) -> WorkspaceMembership:
        row = connection.execute(
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
                self._workspace_id,
                membership_id,
            ),
        ).fetchone()

        if row is None:
            raise WorkspaceMembershipNotFoundError(
                "Workspace membership does not exist."
            )

        return self._membership_from_row(row)

    @staticmethod
    def _membership_from_row(
        row: sqlite3.Row,
    ) -> WorkspaceMembership:
        return WorkspaceMembership(
            membership_id=row["membership_id"],
            workspace_id=row["workspace_id"],
            principal_id=row["principal_id"],
            status=row["status"],
            role=row["role"],
            revision=int(row["revision"]),
            created_by_principal_id=row[
                "created_by_principal_id"
            ],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status_changed_at=row[
                "status_changed_at"
            ],
        )

    def _current_membership_exists(
        self,
        connection: sqlite3.Connection,
        principal_id: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1
            FROM workspace_memberships
            WHERE
                workspace_id = ?
                AND principal_id = ?
                AND status != 'removed'
            LIMIT 1
            """,
            (
                self._workspace_id,
                principal_id,
            ),
        ).fetchone()

        return row is not None

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
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
