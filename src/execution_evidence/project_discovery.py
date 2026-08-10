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

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


MAX_PROJECT_DISCOVERY_RESULTS = 500

MAX_PROJECT_DISCOVERY_CURSOR_BYTES = 512

MAX_PROJECT_DISCOVERY_CURSOR_PROJECT_ID_LENGTH = 256

PROJECT_DISCOVERY_CURSOR_VERSION = 1


ProjectDiscoveryStatus = Literal[
    "active",
    "archived",
    "deleted",
]


class ProjectDiscoveryError(RuntimeError):
    pass


class ProjectDiscoveryStoreError(
    ProjectDiscoveryError
):
    pass


class DiscoveredProject(BaseModel):
    """One project discoverable inside an authorized workspace."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: ProjectDiscoveryStatus
    revision: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime

    @field_validator(
        "created_at",
        "updated_at",
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
                "Project discovery timestamps must "
                "be timezone-aware."
            )

        return value


class ProjectDiscoveryResult(BaseModel):
    """Bounded workspace-scoped project discovery result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    projects: List[DiscoveredProject]
    truncated: bool
    next_cursor: Optional[str] = None


class SQLiteProjectDiscoveryService:
    """Discover active projects inside one authorized workspace.

    This service does not perform tenancy or capability
    authorization. The API must supply the workspace identity
    from an AuthorizedWorkspaceContext after authenticating and
    authorizing the request.

    Active projects are ordered by immutable project identity
    fields:

        project.created_at DESC,
        project.project_id ASC

    The project_id tiebreaker is unique inside a workspace
    because projects enforce UNIQUE(workspace_id, project_id).

    Cursor pagination is live rather than snapshot-isolated.
    Existing project rows cannot move across page boundaries
    because Migration 26 makes workspace_id, project_id, and
    created_at immutable.

    The continuation predicate compares the exact persisted
    created_at text. Textually distinct timestamps occupy
    distinct primary sort positions and are handled by the
    created_at inequality branch. The project_id equality branch
    is used only when persisted created_at strings are identical.
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
        workspace_id: str,
        cursor: Optional[str] = None,
        page_size: Optional[int] = None,
    ) -> ProjectDiscoveryResult:
        self._validate_workspace_id(
            workspace_id
        )

        resolved_page_size = (
            MAX_PROJECT_DISCOVERY_RESULTS
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
                "Project discovery page size must "
                "be an integer."
            )

        if (
            resolved_page_size < 1
            or resolved_page_size
            > MAX_PROJECT_DISCOVERY_RESULTS
        ):
            raise ValueError(
                "Project discovery page size must "
                "be between 1 and "
                f"{MAX_PROJECT_DISCOVERY_RESULTS}."
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
                        project.project_id,
                        project.title,
                        project.status,
                        project.revision,
                        project.created_at,
                        project.updated_at
                    FROM projects AS project
                    WHERE
                        project.workspace_id = ?
                        AND project.status = 'active'
                    ORDER BY
                        project.created_at DESC,
                        project.project_id ASC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        resolved_page_size + 1,
                    ),
                ).fetchall()

            else:
                boundary_created_at = (
                    boundary["created_at"]
                )
                boundary_project_id = (
                    boundary["project_id"]
                )

                rows = connection.execute(
                    """
                    SELECT
                        project.project_id,
                        project.title,
                        project.status,
                        project.revision,
                        project.created_at,
                        project.updated_at
                    FROM projects AS project
                    WHERE
                        project.workspace_id = ?
                        AND project.status = 'active'
                        AND (
                            project.created_at < ?
                            OR (
                                project.created_at = ?
                                AND project.project_id > ?
                            )
                        )
                    ORDER BY
                        project.created_at DESC,
                        project.project_id ASC
                    LIMIT ?
                    """,
                    (
                        workspace_id,
                        boundary_created_at,
                        boundary_created_at,
                        boundary_project_id,
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

            projects = [
                DiscoveredProject(
                    project_id=row["project_id"],
                    title=row["title"],
                    status=row["status"],
                    revision=int(row["revision"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in bounded_rows
            ]

            next_cursor = None

            if truncated and bounded_rows:
                last_row = bounded_rows[-1]

                next_cursor = self._encode_cursor(
                    created_at=str(
                        last_row["created_at"]
                    ),
                    project_id=str(
                        last_row["project_id"]
                    ),
                )

            return ProjectDiscoveryResult(
                projects=projects,
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

            raise ProjectDiscoveryStoreError(
                "Could not discover workspace projects."
            ) from error

        finally:
            connection.close()

    def list_active(
        self,
        *,
        workspace_id: str,
    ) -> List[DiscoveredProject]:
        """Compatibility helper returning only the bounded list."""

        return self.discover(
            workspace_id=workspace_id
        ).projects

    @classmethod
    def _encode_cursor(
        cls,
        *,
        created_at: str,
        project_id: str,
    ) -> str:
        payload = {
            "created_at": created_at,
            "project_id": project_id,
            "v": PROJECT_DISCOVERY_CURSOR_VERSION,
        }

        raw = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

        encoded = (
            base64.urlsafe_b64encode(raw)
            .decode("ascii")
            .rstrip("=")
        )

        if (
            len(encoded.encode("utf-8"))
            > MAX_PROJECT_DISCOVERY_CURSOR_BYTES
        ):
            raise ValueError(
                "Project discovery cursor exceeds "
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
                "Project discovery cursor is invalid."
            )

        if (
            not cursor
            or cursor != cursor.strip()
        ):
            raise ValueError(
                "Project discovery cursor is invalid."
            )

        encoded_size = len(
            cursor.encode("utf-8")
        )

        if (
            encoded_size
            > MAX_PROJECT_DISCOVERY_CURSOR_BYTES
        ):
            raise ValueError(
                "Project discovery cursor exceeds "
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
                "Project discovery cursor is invalid."
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
                "Project discovery cursor is invalid."
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
                "Project discovery cursor is invalid."
            ) from error

        if not isinstance(payload, dict):
            raise ValueError(
                "Project discovery cursor is invalid."
            )

        if set(payload) != {
            "created_at",
            "project_id",
            "v",
        }:
            raise ValueError(
                "Project discovery cursor is invalid."
            )

        version = payload["v"]

        if (
            type(version) is not int
            or version
            != PROJECT_DISCOVERY_CURSOR_VERSION
        ):
            raise ValueError(
                "Project discovery cursor version "
                "is unsupported."
            )

        created_at = payload["created_at"]

        if (
            not isinstance(created_at, str)
            or not created_at
            or created_at != created_at.strip()
        ):
            raise ValueError(
                "Project discovery cursor timestamp "
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
                "Project discovery cursor timestamp "
                "is invalid."
            ) from error

        if (
            parsed.tzinfo is None
            or parsed.utcoffset() is None
        ):
            raise ValueError(
                "Project discovery cursor timestamp "
                "must be timezone-aware."
            )

        project_id = payload["project_id"]

        if (
            not isinstance(project_id, str)
            or not project_id
            or project_id != project_id.strip()
            or len(project_id)
            > MAX_PROJECT_DISCOVERY_CURSOR_PROJECT_ID_LENGTH
        ):
            raise ValueError(
                "Project discovery cursor project "
                "identity is invalid."
            )

        return {
            "created_at": created_at,
            "project_id": project_id,
        }

    @staticmethod
    def _validate_workspace_id(
        workspace_id: str,
    ) -> None:
        if not isinstance(workspace_id, str):
            raise TypeError(
                "Workspace ID must be text."
            )

        if not workspace_id:
            raise ValueError(
                "Workspace ID must be non-empty."
            )

        if workspace_id != workspace_id.strip():
            raise ValueError(
                "Workspace ID must not contain "
                "surrounding whitespace."
            )
