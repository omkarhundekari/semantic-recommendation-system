from __future__ import annotations

import hashlib
import json
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


class WorkspaceProvisioningIdempotencyConflictError(
    WorkspaceProvisioningError
):
    """Idempotency key was reused for different content."""

    pass


class WorkspaceProvisioningUnavailableError(
    WorkspaceProvisioningError
):
    """Provisioning storage is temporarily unavailable."""

    pass


class WorkspaceProvisioningIdempotentResult(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    result: WorkspaceProvisioningResult
    replayed: bool


WORKSPACE_PROVISIONING_OPERATION = (
    "workspace.provision.v1"
)


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

            result = self._provision_on_connection(
                connection,
                principal_id=principal_id,
                created_at=created_at,
                normalized_reason=(
                    normalized_reason
                ),
            )

            connection.execute("COMMIT")
            return result

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

    def provision_idempotent(
        self,
        *,
        principal_id: str,
        idempotency_key: str,
        created_at: datetime,
        reason: Optional[str] = None,
    ) -> WorkspaceProvisioningIdempotentResult:
        self._validate_identifier(
            principal_id,
            name="Principal ID",
        )
        self._validate_idempotency_key(
            idempotency_key
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

        request_fingerprint = (
            self._provisioning_request_fingerprint(
                principal_id=principal_id,
                normalized_reason=(
                    normalized_reason
                ),
            )
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                """
                SELECT
                    principal_id,
                    idempotency_key,
                    operation,
                    request_fingerprint,
                    workspace_id,
                    membership_id,
                    owner_role_transition_id,
                    created_at
                FROM workspace_provisioning_idempotency
                WHERE
                    principal_id = ?
                    AND idempotency_key = ?
                """,
                (
                    principal_id,
                    idempotency_key,
                ),
            ).fetchone()

            if existing is not None:
                if (
                    existing["operation"]
                    != WORKSPACE_PROVISIONING_OPERATION
                    or existing["request_fingerprint"]
                    != request_fingerprint
                ):
                    raise (
                        WorkspaceProvisioningIdempotencyConflictError(
                            "Workspace provisioning "
                            "idempotency key was reused "
                            "with different request "
                            "content."
                        )
                    )

                replay = (
                    self._load_provisioning_replay_on_connection(
                        connection,
                        ledger_row=existing,
                        normalized_reason=(
                            normalized_reason
                        ),
                    )
                )

                connection.execute("COMMIT")

                return WorkspaceProvisioningIdempotentResult(
                    result=replay,
                    replayed=True,
                )

            # Creation branch only:
            # revalidate current principal authority before
            # granting new workspace ownership.
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

            provisioned = self._provision_on_connection(
                connection,
                principal_id=principal_id,
                created_at=created_at,
                normalized_reason=(
                    normalized_reason
                ),
            )

            connection.execute(
                """
                INSERT INTO workspace_provisioning_idempotency (
                    principal_id,
                    idempotency_key,
                    operation,
                    request_fingerprint,
                    workspace_id,
                    membership_id,
                    owner_role_transition_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    principal_id,
                    idempotency_key,
                    WORKSPACE_PROVISIONING_OPERATION,
                    request_fingerprint,
                    (
                        provisioned
                        .workspace
                        .workspace_id
                    ),
                    (
                        provisioned
                        .membership
                        .membership_id
                    ),
                    (
                        provisioned
                        .owner_transition
                        .transition_id
                    ),
                    created_at.isoformat(),
                ),
            )

            ledger = connection.execute(
                """
                SELECT
                    principal_id,
                    idempotency_key,
                    operation,
                    request_fingerprint,
                    workspace_id,
                    membership_id,
                    owner_role_transition_id,
                    created_at
                FROM workspace_provisioning_idempotency
                WHERE
                    principal_id = ?
                    AND idempotency_key = ?
                """,
                (
                    principal_id,
                    idempotency_key,
                ),
            ).fetchone()

            if ledger is None:
                raise WorkspaceProvisioningStateError(
                    "Workspace provisioning "
                    "idempotency record disappeared "
                    "before commit."
                )

            if (
                ledger["operation"]
                != WORKSPACE_PROVISIONING_OPERATION
                or ledger["request_fingerprint"]
                != request_fingerprint
                or ledger["workspace_id"]
                != provisioned.workspace.workspace_id
                or ledger["membership_id"]
                != provisioned.membership.membership_id
                or ledger["owner_role_transition_id"]
                != provisioned.owner_transition.transition_id
            ):
                raise WorkspaceProvisioningStateError(
                    "Workspace provisioning "
                    "idempotency record is not "
                    "authoritative."
                )

            connection.execute("COMMIT")

            return WorkspaceProvisioningIdempotentResult(
                result=provisioned,
                replayed=False,
            )

        except (
            WorkspaceProvisioningIdempotencyConflictError,
            WorkspaceProvisioningPrincipalUnavailableError,
            WorkspaceProvisioningIdentityCollisionError,
            WorkspaceProvisioningStateError,
        ):
            self._rollback(connection)
            raise
        except ValueError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise WorkspaceProvisioningStateError(
                "Workspace provisioning "
                "idempotency transaction violated "
                "a storage integrity constraint."
            ) from error
        except sqlite3.OperationalError as error:
            self._rollback(connection)

            if self._is_sqlite_busy_error(error):
                raise WorkspaceProvisioningUnavailableError(
                    "Workspace provisioning storage "
                    "is temporarily busy."
                ) from error

            raise WorkspaceProvisioningError(
                "Could not provision workspace "
                "idempotently."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise WorkspaceProvisioningError(
                "Could not provision workspace "
                "idempotently."
            ) from error
        finally:
            connection.close()

    def _load_provisioning_replay_on_connection(
        self,
        connection: sqlite3.Connection,
        *,
        ledger_row: sqlite3.Row,
        normalized_reason: Optional[str],
    ) -> WorkspaceProvisioningResult:
        """Reload a completed provisioning graph.

        Replay verifies durable identity and historical
        linkage only. Current membership status, role, and
        revision may legitimately have changed after the
        original provisioning operation.
        """

        if not connection.in_transaction:
            raise ValueError(
                "Workspace provisioning replay requires "
                "an active caller-owned transaction."
            )

        principal_id = str(
            ledger_row["principal_id"]
        )
        workspace_id = str(
            ledger_row["workspace_id"]
        )
        membership_id = str(
            ledger_row["membership_id"]
        )
        transition_id = str(
            ledger_row["owner_role_transition_id"]
        )

        workspace_row = connection.execute(
            """
            SELECT
                workspace_id,
                workspace_kind,
                created_at,
                updated_at
            FROM workspaces
            WHERE workspace_id = ?
            """,
            (workspace_id,),
        ).fetchone()

        membership_row = connection.execute(
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
            WHERE membership_id = ?
            """,
            (membership_id,),
        ).fetchone()

        transition_row = connection.execute(
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
            (transition_id,),
        ).fetchone()

        if (
            workspace_row is None
            or membership_row is None
            or transition_row is None
        ):
            raise WorkspaceProvisioningStateError(
                "Workspace provisioning replay graph "
                "is incomplete."
            )

        if (
            workspace_row["workspace_id"]
            != workspace_id
            or workspace_row["workspace_kind"]
            != "provisioned"
            or membership_row["membership_id"]
            != membership_id
            or membership_row["workspace_id"]
            != workspace_id
            or membership_row["principal_id"]
            != principal_id
            or transition_row["role_transition_id"]
            != transition_id
            or transition_row["membership_id"]
            != membership_id
            or transition_row["workspace_id"]
            != workspace_id
            or transition_row["principal_id"]
            != principal_id
        ):
            raise WorkspaceProvisioningStateError(
                "Workspace provisioning replay graph "
                "identity linkage is invalid."
            )

        # Historical first-owner transition is immutable.
        # Verify the original provisioning edge, but do not
        # require the membership's current role/revision/status
        # to remain at its provisioning-time values.
        if (
            transition_row["previous_role"]
            is not None
            or transition_row["new_role"]
            != "owner"
            or int(
                transition_row[
                    "previous_revision"
                ]
            )
            != 0
            or int(
                transition_row[
                    "resulting_revision"
                ]
            )
            != 1
            or transition_row[
                "changed_by_principal_id"
            ]
            is not None
            or transition_row["reason"]
            != normalized_reason
        ):
            raise WorkspaceProvisioningStateError(
                "Workspace provisioning replay "
                "historical owner transition is "
                "invalid."
            )

        workspace = ProvisionedWorkspace(
            workspace_id=workspace_row[
                "workspace_id"
            ],
            workspace_kind=workspace_row[
                "workspace_kind"
            ],
            created_at=workspace_row[
                "created_at"
            ],
            updated_at=workspace_row[
                "updated_at"
            ],
        )

        membership = WorkspaceMembership(
            membership_id=membership_row[
                "membership_id"
            ],
            workspace_id=membership_row[
                "workspace_id"
            ],
            principal_id=membership_row[
                "principal_id"
            ],
            status=membership_row["status"],
            role=membership_row["role"],
            revision=int(
                membership_row["revision"]
            ),
            created_by_principal_id=(
                membership_row[
                    "created_by_principal_id"
                ]
            ),
            created_at=membership_row[
                "created_at"
            ],
            updated_at=membership_row[
                "updated_at"
            ],
            status_changed_at=membership_row[
                "status_changed_at"
            ],
        )

        owner_transition = (
            WorkspaceMembershipRoleTransition(
                transition_id=transition_row[
                    "role_transition_id"
                ],
                membership_id=transition_row[
                    "membership_id"
                ],
                workspace_id=transition_row[
                    "workspace_id"
                ],
                principal_id=transition_row[
                    "principal_id"
                ],
                previous_role=transition_row[
                    "previous_role"
                ],
                new_role=transition_row[
                    "new_role"
                ],
                previous_revision=int(
                    transition_row[
                        "previous_revision"
                    ]
                ),
                resulting_revision=int(
                    transition_row[
                        "resulting_revision"
                    ]
                ),
                changed_at=transition_row[
                    "changed_at"
                ],
                changed_by_principal_id=(
                    transition_row[
                        "changed_by_principal_id"
                    ]
                ),
                reason=transition_row["reason"],
            )
        )

        return WorkspaceProvisioningResult(
            workspace=workspace,
            membership=membership,
            owner_transition=owner_transition,
        )

    @staticmethod
    def _provisioning_request_fingerprint(
        *,
        principal_id: str,
        normalized_reason: Optional[str],
    ) -> str:
        canonical = json.dumps(
            {
                "operation": (
                    WORKSPACE_PROVISIONING_OPERATION
                ),
                "principal_id": principal_id,
                "reason": normalized_reason,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _validate_idempotency_key(
        idempotency_key: str,
    ) -> None:
        if not isinstance(
            idempotency_key,
            str,
        ):
            raise TypeError(
                "Workspace provisioning "
                "idempotency key must be a string."
            )

        if not idempotency_key:
            raise ValueError(
                "Workspace provisioning "
                "idempotency key must be non-empty."
            )

        if len(idempotency_key) > 255:
            raise ValueError(
                "Workspace provisioning "
                "idempotency key must not exceed "
                "255 characters."
            )

    @staticmethod
    def _is_sqlite_busy_error(
        error: sqlite3.OperationalError,
    ) -> bool:
        code = getattr(
            error,
            "sqlite_errorcode",
            None,
        )

        if code in {
            getattr(
                sqlite3,
                "SQLITE_BUSY",
                None,
            ),
            getattr(
                sqlite3,
                "SQLITE_LOCKED",
                None,
            ),
        }:
            return True

        message = str(error).lower()

        return (
            "database is locked" in message
            or "database is busy" in message
            or "database table is locked" in message
        )

    def _provision_on_connection(
        self,
        connection: sqlite3.Connection,
        *,
        principal_id: str,
        created_at: datetime,
        normalized_reason: Optional[str],
    ) -> WorkspaceProvisioningResult:
        """Provision inside a caller-owned transaction.

        The caller owns connection lifecycle and transaction
        boundaries. This helper never begins, commits, rolls
        back, opens, or closes a SQLite connection.

        The provisioning principal must already have been
        validated for the creation operation.
        """

        if not connection.in_transaction:
            raise ValueError(
                "Workspace provisioning requires an "
                "active caller-owned transaction."
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

        return WorkspaceProvisioningResult(
            workspace=stored_workspace,
            membership=stored_membership,
            owner_transition=owner_transition,
        )

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
