from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from execution_evidence.authorized_project_context import (
    AuthorizedProjectContext,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class ProjectReadError(RuntimeError):
    pass


class ProjectReadNotFoundError(
    ProjectReadError
):
    pass


class ProjectReadStoreError(
    ProjectReadError
):
    pass


class ProjectReadRecord(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: str
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
                "Project read timestamps must "
                "be timezone-aware."
            )

        return value


class SQLiteProjectReadService:
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def load(
        self,
        context: AuthorizedProjectContext,
    ) -> ProjectReadRecord:
        if not isinstance(
            context,
            AuthorizedProjectContext,
        ):
            raise TypeError(
                "Authorized project context is required."
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
                    project_id,
                    title,
                    status,
                    revision,
                    created_at,
                    updated_at
                FROM projects
                WHERE
                    workspace_id = ?
                    AND project_id = ?
                LIMIT 1
                """,
                (
                    context.workspace_id,
                    context.project_id,
                ),
            ).fetchone()

            if row is None:
                raise ProjectReadNotFoundError(
                    "Project does not exist."
                )

            try:
                return ProjectReadRecord(
                    project_id=row["project_id"],
                    title=row["title"],
                    status=row["status"],
                    revision=int(row["revision"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ProjectReadStoreError(
                    "Stored project metadata is invalid."
                ) from error

        except (
            ProjectReadNotFoundError,
            ProjectReadStoreError,
        ):
            raise
        except sqlite3.Error as error:
            raise ProjectReadStoreError(
                "Could not load project."
            ) from error
        finally:
            connection.close()
