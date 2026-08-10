from __future__ import annotations

import base64
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

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
MAX_WORKSPACE_DISCOVERY_CURSOR_BYTES = 512
WORKSPACE_DISCOVERY_CURSOR_VERSION = 1
MAX_WORKSPACE_DISCOVERY_CURSOR_WORKSPACE_ID_LENGTH = 255


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
    next_cursor: Optional[str] = None


class SQLiteWorkspaceDiscoveryService:
    """Discover current workspaces visible to one principal.

    Discovery is principal-scoped and does not trust caller-
    supplied workspace identities.

    A workspace is discoverable only through an active
    membership with a currently assigned role and an active
    durable principal.

    Removed, suspended, and role-less memberships are excluded.

    Results use immutable membership creation time for stable
    keyset pagination:

        membership.created_at DESC,
        membership.workspace_id ASC

    Cursor pagination is live rather than snapshot-isolated
    across HTTP requests. Existing rows cannot move across page
    boundaries because membership.created_at is immutable.
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
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> WorkspaceDiscoveryResult:
        if not isinstance(
            principal,
            AuthenticatedRequestPrincipal,
        ):
            raise TypeError(
                "Workspace discovery requires an "
                "authenticated request principal."
            )

        resolved_page_size = (
            MAX_WORKSPACE_DISCOVERY_RESULTS
            if page_size is None
            else page_size
        )

        if (
            isinstance(resolved_page_size, bool)
            or not isinstance(
                resolved_page_size,
                int,
            )
        ):
            raise ValueError(
                "Workspace discovery page size must "
                "be an integer."
            )

        if (
            resolved_page_size < 1
            or resolved_page_size
            > MAX_WORKSPACE_DISCOVERY_RESULTS
        ):
            raise ValueError(
                "Workspace discovery page size must "
                "be between 1 and "
                f"{MAX_WORKSPACE_DISCOVERY_RESULTS}."
            )

        boundary = (
            self._decode_cursor(cursor)
            if cursor is not None
            else None
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN")

            if boundary is None:
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
                        membership.created_at DESC,
                        membership.workspace_id ASC
                    LIMIT ?
                    """,
                    (
                        principal.principal_id,
                        resolved_page_size + 1,
                    ),
                ).fetchall()
            else:
                boundary_created_at = (
                    boundary["created_at"]
                )
                boundary_workspace_id = (
                    boundary["workspace_id"]
                )

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
                        AND (
                            membership.created_at < ?
                            OR (
                                membership.created_at = ?
                                AND membership.workspace_id > ?
                            )
                        )
                    ORDER BY
                        membership.created_at DESC,
                        membership.workspace_id ASC
                    LIMIT ?
                    """,
                    (
                        principal.principal_id,
                        boundary_created_at,
                        boundary_created_at,
                        boundary_workspace_id,
                        resolved_page_size + 1,
                    ),
                ).fetchall()

            if connection.in_transaction:
                connection.rollback()

            truncated = (
                len(rows)
                > resolved_page_size
            )

            bounded_rows = rows[
                :resolved_page_size
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

            next_cursor = None

            if truncated and bounded_rows:
                last_row = bounded_rows[-1]

                # Preserve the exact persisted text representation.
                next_cursor = self._encode_cursor(
                    created_at=str(
                        last_row[
                            "membership_created_at"
                        ]
                    ),
                    workspace_id=str(
                        last_row["workspace_id"]
                    ),
                )

            return WorkspaceDiscoveryResult(
                workspaces=workspaces,
                truncated=truncated,
                next_cursor=next_cursor,
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
        """Return the bounded workspace list only."""

        return self.discover(
            principal=principal
        ).workspaces

    @classmethod
    def _encode_cursor(
        cls,
        *,
        created_at: str,
        workspace_id: str,
    ) -> str:
        payload = {
            "created_at": created_at,
            "v": WORKSPACE_DISCOVERY_CURSOR_VERSION,
            "workspace_id": workspace_id,
        }

        serialized = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        encoded = (
            base64.urlsafe_b64encode(
                serialized
            )
            .decode("ascii")
            .rstrip("=")
        )

        if (
            len(encoded.encode("ascii"))
            > MAX_WORKSPACE_DISCOVERY_CURSOR_BYTES
        ):
            raise ValueError(
                "Workspace discovery cursor exceeds "
                "the supported size."
            )

        return encoded

    @classmethod
    def _decode_cursor(
        cls,
        cursor: str,
    ) -> dict:
        if not isinstance(cursor, str):
            raise ValueError(
                "Workspace discovery cursor is invalid."
            )

        if (
            not cursor
            or cursor != cursor.strip()
        ):
            raise ValueError(
                "Workspace discovery cursor is invalid."
            )

        encoded_size = len(
            cursor.encode("utf-8")
        )

        if (
            encoded_size
            > MAX_WORKSPACE_DISCOVERY_CURSOR_BYTES
        ):
            raise ValueError(
                "Workspace discovery cursor exceeds "
                "the supported size."
            )

        if (
            re.fullmatch(
                r"[A-Za-z0-9_-]+",
                cursor,
            )
            is None
        ):
            raise ValueError(
                "Workspace discovery cursor is invalid."
            )

        padding = "=" * (
            (-len(cursor)) % 4
        )

        try:
            decoded = base64.urlsafe_b64decode(
                cursor + padding
            )
        except Exception as error:
            raise ValueError(
                "Workspace discovery cursor is invalid."
            ) from error

        try:
            payload = json.loads(
                decoded.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError(
                "Workspace discovery cursor is invalid."
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(
                "Workspace discovery cursor is invalid."
            )

        if set(payload) != {
            "created_at",
            "v",
            "workspace_id",
        }:
            raise ValueError(
                "Workspace discovery cursor is invalid."
            )

        version = payload["v"]

        if (
            type(version) is not int
            or version
            != WORKSPACE_DISCOVERY_CURSOR_VERSION
        ):
            raise ValueError(
                "Workspace discovery cursor version "
                "is unsupported."
            )

        created_at = payload["created_at"]

        if (
            not isinstance(created_at, str)
            or not created_at
            or created_at != created_at.strip()
        ):
            raise ValueError(
                "Workspace discovery cursor timestamp "
                "is invalid."
            )

        parse_value = created_at

        if parse_value.endswith("Z"):
            parse_value = (
                parse_value[:-1] + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                parse_value
            )
        except ValueError as error:
            raise ValueError(
                "Workspace discovery cursor timestamp "
                "is invalid."
            ) from error

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            raise ValueError(
                "Workspace discovery cursor timestamp "
                "must be timezone-aware."
            )

        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError(
                "Workspace discovery cursor timestamp "
                "must use UTC."
            )

        workspace_id = payload[
            "workspace_id"
        ]

        if (
            not isinstance(workspace_id, str)
            or not workspace_id
            or workspace_id
            != workspace_id.strip()
            or len(workspace_id)
            > MAX_WORKSPACE_DISCOVERY_CURSOR_WORKSPACE_ID_LENGTH
        ):
            raise ValueError(
                "Workspace discovery cursor workspace "
                "identity is invalid."
            )

        return {
            "created_at": created_at,
            "workspace_id": workspace_id,
        }
