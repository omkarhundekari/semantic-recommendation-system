from __future__ import annotations

import sqlite3
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class PrincipalProfileReadError(RuntimeError):
    pass


class PrincipalProfileNotFoundError(
    PrincipalProfileReadError
):
    """Durable principal is missing or no longer active."""


class PrincipalProfile(BaseModel):
    """Minimal browser-safe durable principal profile.

    This deliberately excludes:

    - external identity subject;
    - identity-provider identifiers;
    - identity-link identifiers;
    - login-session identifiers;
    - workspace or project membership.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    principal_id: str = Field(
        min_length=1,
    )

    principal_kind: str = Field(
        min_length=1,
    )

    @field_validator(
        "principal_id",
        "principal_kind",
    )
    @classmethod
    def require_exact_text(
        cls,
        value: str,
    ) -> str:
        if (
            not value
            or value != value.strip()
        ):
            raise ValueError(
                "Principal profile values must be "
                "non-empty exact text."
            )

        return value


class SQLitePrincipalProfileReader:
    """Read minimal durable principal metadata.

    Authentication remains the responsibility of
    RequestAuthenticator.

    This reader receives an already-authenticated durable
    principal ID and exposes only browser-safe principal
    metadata.
    """

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(
            path
        )

    @property
    def path(
        self,
    ) -> Path:
        return self._path

    def read(
        self,
        principal_id: str,
    ) -> PrincipalProfile:
        if (
            not isinstance(
                principal_id,
                str,
            )
            or not principal_id
            or principal_id
                != principal_id.strip()
        ):
            raise ValueError(
                "principal_id must be non-empty "
                "exact text."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute(
                "BEGIN"
            )

            try:
                row = connection.execute(
                    """
                    SELECT
                        principal_id,
                        principal_kind
                    FROM principals
                    WHERE
                        principal_id = ?
                        AND status = 'active'
                    """,
                    (
                        principal_id,
                    ),
                ).fetchone()

            finally:
                if connection.in_transaction:
                    connection.rollback()

        except sqlite3.Error as error:
            raise PrincipalProfileReadError(
                "Principal profile storage is "
                "temporarily unavailable."
            ) from error

        finally:
            connection.close()

        if row is None:
            raise PrincipalProfileNotFoundError(
                "Principal profile is not active."
            )

        return PrincipalProfile(
            principal_id=row[
                "principal_id"
            ],
            principal_kind=row[
                "principal_kind"
            ],
        )
