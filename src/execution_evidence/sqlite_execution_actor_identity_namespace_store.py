from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from execution_evidence.execution_actor_identity_namespace import (
    ExecutionActorIdentityNamespace,
)
from execution_evidence.execution_actor_identity_namespace_store import (
    ExecutionActorIdentityNamespaceAlreadyExistsError,
    ExecutionActorIdentityNamespaceNotFoundError,
    ExecutionActorIdentityNamespaceProviderNotFoundError,
    ExecutionActorIdentityNamespaceStore,
    ExecutionActorIdentityNamespaceStoreError,
    ExecutionActorIdentityNamespaceTransitionError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLiteExecutionActorIdentityNamespaceStore(
    ExecutionActorIdentityNamespaceStore
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
        namespace: ExecutionActorIdentityNamespace,
    ) -> ExecutionActorIdentityNamespace:
        if (
            namespace.retired_at is not None
            or namespace.retired_reason is not None
        ):
            raise (
                ExecutionActorIdentityNamespaceTransitionError(
                    "New execution actor identity "
                    "namespaces must begin current."
                )
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            provider = connection.execute(
                """
                SELECT identity_provider_id
                FROM identity_providers
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                """,
                (
                    namespace.identity_provider_id,
                    namespace.issuer,
                ),
            ).fetchone()

            if provider is None:
                raise (
                    ExecutionActorIdentityNamespaceProviderNotFoundError(
                        "Identity provider does not "
                        "exist for the supplied issuer."
                    )
                )

            connection.execute(
                """
                INSERT INTO execution_actor_identity_namespaces (
                    execution_actor_namespace_id,
                    source_provider,
                    identity_provider_id,
                    issuer,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (
                    ?, ?, ?, ?, ?, NULL, NULL
                )
                """,
                (
                    namespace.execution_actor_namespace_id,
                    namespace.source_provider,
                    namespace.identity_provider_id,
                    namespace.issuer,
                    namespace.created_at.isoformat(),
                ),
            )

            stored = self._load_from_connection(
                connection,
                namespace.execution_actor_namespace_id,
            )

            if stored != namespace:
                raise ExecutionActorIdentityNamespaceStoreError(
                    "Stored execution actor identity "
                    "namespace does not match "
                    "authoritative state."
                )

            connection.execute("COMMIT")
            return stored

        except (
            ExecutionActorIdentityNamespaceStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)

            message = str(error)

            if (
                "UNIQUE constraint failed: "
                "execution_actor_identity_namespaces."
                "execution_actor_namespace_id"
                in message
                or
                "UNIQUE constraint failed: "
                "execution_actor_identity_namespaces."
                "source_provider"
                in message
            ):
                raise (
                    ExecutionActorIdentityNamespaceAlreadyExistsError(
                        "Execution actor identity "
                        "namespace already exists."
                    )
                ) from error

            raise ExecutionActorIdentityNamespaceStoreError(
                "Could not create execution actor "
                "identity namespace."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise ExecutionActorIdentityNamespaceStoreError(
                "Could not create execution actor "
                "identity namespace."
            ) from error
        finally:
            connection.close()

    def load(
        self,
        execution_actor_namespace_id: str,
    ) -> ExecutionActorIdentityNamespace:
        self._validate_exact_value(
            execution_actor_namespace_id,
            name="Execution actor namespace ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_from_connection(
                connection,
                execution_actor_namespace_id,
            )
        except ExecutionActorIdentityNamespaceNotFoundError:
            raise
        except sqlite3.Error as error:
            raise ExecutionActorIdentityNamespaceStoreError(
                "Could not load execution actor "
                "identity namespace."
            ) from error
        finally:
            connection.close()

    def load_current_by_source_provider(
        self,
        source_provider: str,
    ) -> ExecutionActorIdentityNamespace:
        if not isinstance(source_provider, str):
            raise ValueError(
                "Source provider must be text."
            )

        if not source_provider:
            raise ValueError(
                "Source provider must be non-empty."
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
                    execution_actor_namespace_id,
                    source_provider,
                    identity_provider_id,
                    issuer,
                    created_at,
                    retired_at,
                    retired_reason
                FROM execution_actor_identity_namespaces
                WHERE
                    source_provider = ?
                    AND retired_at IS NULL
                """,
                (source_provider,),
            ).fetchone()

            if row is None:
                raise (
                    ExecutionActorIdentityNamespaceNotFoundError(
                        "Current execution actor identity "
                        "namespace does not exist."
                    )
                )

            return self._namespace_from_row(row)

        except ExecutionActorIdentityNamespaceNotFoundError:
            raise
        except sqlite3.Error as error:
            raise ExecutionActorIdentityNamespaceStoreError(
                "Could not load current execution actor "
                "identity namespace."
            ) from error
        finally:
            connection.close()

    def list_for_identity_provider(
        self,
        identity_provider_id: str,
    ) -> List[ExecutionActorIdentityNamespace]:
        self._validate_exact_value(
            identity_provider_id,
            name="Identity provider ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            rows = connection.execute(
                """
                SELECT
                    execution_actor_namespace_id,
                    source_provider,
                    identity_provider_id,
                    issuer,
                    created_at,
                    retired_at,
                    retired_reason
                FROM execution_actor_identity_namespaces
                WHERE identity_provider_id = ?
                ORDER BY
                    created_at ASC,
                    execution_actor_namespace_row_id ASC
                """,
                (identity_provider_id,),
            ).fetchall()

            return [
                self._namespace_from_row(row)
                for row in rows
            ]

        except sqlite3.Error as error:
            raise ExecutionActorIdentityNamespaceStoreError(
                "Could not list execution actor "
                "identity namespaces."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_from_connection(
        connection: sqlite3.Connection,
        execution_actor_namespace_id: str,
    ) -> ExecutionActorIdentityNamespace:
        row = connection.execute(
            """
            SELECT
                execution_actor_namespace_id,
                source_provider,
                identity_provider_id,
                issuer,
                created_at,
                retired_at,
                retired_reason
            FROM execution_actor_identity_namespaces
            WHERE execution_actor_namespace_id = ?
            """,
            (execution_actor_namespace_id,),
        ).fetchone()

        if row is None:
            raise (
                ExecutionActorIdentityNamespaceNotFoundError(
                    "Execution actor identity namespace "
                    "does not exist."
                )
            )

        return (
            SQLiteExecutionActorIdentityNamespaceStore
            ._namespace_from_row(row)
        )

    @staticmethod
    def _namespace_from_row(
        row: sqlite3.Row,
    ) -> ExecutionActorIdentityNamespace:
        return ExecutionActorIdentityNamespace(
            execution_actor_namespace_id=row[
                "execution_actor_namespace_id"
            ],
            source_provider=row["source_provider"],
            identity_provider_id=row[
                "identity_provider_id"
            ],
            issuer=row["issuer"],
            created_at=row["created_at"],
            retired_at=row["retired_at"],
            retired_reason=row["retired_reason"],
        )

    @staticmethod
    def _validate_exact_value(
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
