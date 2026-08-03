from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.principal import Principal
from execution_evidence.principal_store import (
    PrincipalAlreadyExistsError,
    PrincipalKindNotFoundError,
    PrincipalNotFoundError,
    PrincipalStore,
    PrincipalStoreError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLitePrincipalStore(
    PrincipalStore
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def create(
        self,
        principal: Principal,
    ) -> Principal:
        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            kind = connection.execute(
                """
                SELECT principal_kind
                FROM principal_kinds
                WHERE principal_kind = ?
                """,
                (principal.principal_kind,),
            ).fetchone()

            if kind is None:
                raise PrincipalKindNotFoundError(
                    "Principal kind is not registered."
                )

            existing = connection.execute(
                """
                SELECT principal_id
                FROM principals
                WHERE principal_id = ?
                """,
                (principal.principal_id,),
            ).fetchone()

            if existing is not None:
                raise PrincipalAlreadyExistsError(
                    "Principal already exists."
                )

            connection.execute(
                """
                INSERT INTO principals (
                    principal_id,
                    principal_kind,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    principal.principal_id,
                    principal.principal_kind,
                    principal.status,
                    principal.created_at.isoformat(),
                    principal.updated_at.isoformat(),
                ),
            )

            stored = self._load_from_connection(
                connection,
                principal.principal_id,
            )

            connection.execute("COMMIT")
            return stored
        except PrincipalStoreError:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        except sqlite3.Error as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")

            raise PrincipalStoreError(
                "Could not create principal."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        principal_id: str,
    ) -> Principal:
        if not principal_id:
            raise ValueError(
                "Principal ID must be non-empty."
            )

        if principal_id != principal_id.strip():
            raise ValueError(
                "Principal ID must not contain "
                "surrounding whitespace."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_from_connection(
                connection,
                principal_id,
            )
        except PrincipalNotFoundError:
            raise
        except sqlite3.Error as error:
            raise PrincipalStoreError(
                "Could not load principal."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_from_connection(
        connection: sqlite3.Connection,
        principal_id: str,
    ) -> Principal:
        row = connection.execute(
            """
            SELECT
                principal_id,
                principal_kind,
                status,
                created_at,
                updated_at
            FROM principals
            WHERE principal_id = ?
            """,
            (principal_id,),
        ).fetchone()

        if row is None:
            raise PrincipalNotFoundError(
                "Principal does not exist."
            )

        return Principal(
            principal_id=row["principal_id"],
            principal_kind=row[
                "principal_kind"
            ],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
