from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List, NoReturn, Optional

from execution_evidence.principal_identity import (
    IdentityProvider,
    PrincipalIdentityLink,
)
from execution_evidence.principal_identity_store import (
    IdentityProviderAlreadyExistsError,
    IdentityProviderNotFoundError,
    PrincipalIdentityAlreadyLinkedError,
    PrincipalIdentityLinkNotFoundError,
    PrincipalIdentityLinkTransitionError,
    PrincipalIdentityOwnershipConflictError,
    PrincipalIdentityPrincipalNotFoundError,
    PrincipalIdentityStore,
    PrincipalIdentityStoreError,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SQLitePrincipalIdentityStore(
    PrincipalIdentityStore
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def create_provider(
        self,
        provider: IdentityProvider,
    ) -> IdentityProvider:
        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            connection.execute(
                """
                INSERT INTO identity_providers (
                    identity_provider_id,
                    provider_kind,
                    issuer,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    provider.identity_provider_id,
                    provider.provider_kind,
                    provider.issuer,
                    provider.status,
                    provider.created_at.isoformat(),
                    provider.updated_at.isoformat(),
                ),
            )

            stored = self._load_provider_from_connection(
                connection,
                provider.identity_provider_id,
            )

            connection.execute("COMMIT")
            return stored

        except PrincipalIdentityStoreError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)

            message = str(error)

            if (
                "UNIQUE constraint failed: "
                "identity_providers.identity_provider_id"
                in message
                or
                "UNIQUE constraint failed: "
                "identity_providers.issuer"
                in message
            ):
                raise IdentityProviderAlreadyExistsError(
                    "Identity provider already exists."
                ) from error

            raise PrincipalIdentityStoreError(
                "Could not create identity provider."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise PrincipalIdentityStoreError(
                "Could not create identity provider."
            ) from error
        finally:
            connection.close()

    def load_provider(
        self,
        identity_provider_id: str,
    ) -> IdentityProvider:
        self._validate_identifier(
            identity_provider_id,
            name="Identity provider ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_provider_from_connection(
                connection,
                identity_provider_id,
            )
        except IdentityProviderNotFoundError:
            raise
        except sqlite3.Error as error:
            raise PrincipalIdentityStoreError(
                "Could not load identity provider."
            ) from error
        finally:
            connection.close()

    def create_link(
        self,
        link: PrincipalIdentityLink,
    ) -> PrincipalIdentityLink:
        if link.status != "active":
            raise PrincipalIdentityLinkTransitionError(
                "Principal identity links must begin "
                "active."
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
                    link.identity_provider_id,
                    link.issuer,
                ),
            ).fetchone()

            if provider is None:
                raise IdentityProviderNotFoundError(
                    "Identity provider does not exist "
                    "for the supplied issuer."
                )

            principal = connection.execute(
                """
                SELECT principal_id
                FROM principals
                WHERE principal_id = ?
                """,
                (link.principal_id,),
            ).fetchone()

            if principal is None:
                raise (
                    PrincipalIdentityPrincipalNotFoundError(
                        "Principal does not exist."
                    )
                )

            connection.execute(
                """
                INSERT INTO principal_identity_links (
                    link_id,
                    identity_provider_id,
                    issuer,
                    subject,
                    principal_id,
                    status,
                    linked_at,
                    ended_at,
                    end_reason,
                    ended_by_principal_id,
                    severed_at,
                    severed_reason,
                    severed_by_principal_id
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    NULL, NULL, NULL,
                    NULL, NULL, NULL
                )
                """,
                (
                    link.link_id,
                    link.identity_provider_id,
                    link.issuer,
                    link.subject,
                    link.principal_id,
                    link.status,
                    link.linked_at.isoformat(),
                ),
            )

            stored = self._load_link_from_connection(
                connection,
                link.link_id,
            )

            connection.execute("COMMIT")
            return stored

        except PrincipalIdentityStoreError:
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            self._raise_link_integrity_error(
                error,
                operation="create",
            )
        except sqlite3.Error as error:
            self._rollback(connection)
            raise PrincipalIdentityStoreError(
                "Could not create principal identity "
                "link."
            ) from error
        finally:
            connection.close()

    def load_link(
        self,
        link_id: str,
    ) -> PrincipalIdentityLink:
        self._validate_identifier(
            link_id,
            name="Principal identity link ID",
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            return self._load_link_from_connection(
                connection,
                link_id,
            )
        except PrincipalIdentityLinkNotFoundError:
            raise
        except sqlite3.Error as error:
            raise PrincipalIdentityStoreError(
                "Could not load principal identity "
                "link."
            ) from error
        finally:
            connection.close()

    def load_active_link(
        self,
        *,
        issuer: str,
        subject: str,
    ) -> PrincipalIdentityLink:
        self._validate_exact_value(
            issuer,
            name="Issuer",
        )
        self._validate_exact_value(
            subject,
            name="Subject",
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
                    link_id,
                    identity_provider_id,
                    issuer,
                    subject,
                    principal_id,
                    status,
                    linked_at,
                    ended_at,
                    end_reason,
                    ended_by_principal_id
                FROM principal_identity_links
                WHERE
                    issuer = ?
                    AND subject = ?
                    AND status = 'active'
                """,
                (
                    issuer,
                    subject,
                ),
            ).fetchone()

            if row is None:
                raise PrincipalIdentityLinkNotFoundError(
                    "Active principal identity link "
                    "does not exist."
                )

            return self._link_from_row(row)

        except PrincipalIdentityLinkNotFoundError:
            raise
        except sqlite3.Error as error:
            raise PrincipalIdentityStoreError(
                "Could not load active principal "
                "identity link."
            ) from error
        finally:
            connection.close()

    def list_principal_links(
        self,
        principal_id: str,
    ) -> List[PrincipalIdentityLink]:
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
            rows = connection.execute(
                """
                SELECT
                    link_id,
                    identity_provider_id,
                    issuer,
                    subject,
                    principal_id,
                    status,
                    linked_at,
                    ended_at,
                    end_reason,
                    ended_by_principal_id
                FROM principal_identity_links
                WHERE principal_id = ?
                ORDER BY
                    linked_at ASC,
                    identity_link_row_id ASC
                """,
                (principal_id,),
            ).fetchall()

            return [
                self._link_from_row(row)
                for row in rows
            ]

        except sqlite3.Error as error:
            raise PrincipalIdentityStoreError(
                "Could not list principal identity "
                "links."
            ) from error
        finally:
            connection.close()

    def end_link(
        self,
        link_id: str,
        *,
        ended_at,
        end_reason: str,
        ended_by_principal_id: Optional[str] = None,
    ) -> PrincipalIdentityLink:
        self._validate_identifier(
            link_id,
            name="Principal identity link ID",
        )

        if (
            ended_at.tzinfo is None
            or ended_at.utcoffset() is None
        ):
            raise ValueError(
                "Ended timestamp must be "
                "timezone-aware."
            )

        normalized_reason = end_reason.strip()
        if not normalized_reason:
            raise ValueError(
                "End reason must be non-empty."
            )

        if ended_by_principal_id is not None:
            self._validate_identifier(
                ended_by_principal_id,
                name="Ending principal ID",
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN IMMEDIATE")

            current = self._load_link_from_connection(
                connection,
                link_id,
            )

            if current.status != "active":
                raise PrincipalIdentityLinkTransitionError(
                    "Principal identity link is not "
                    "active."
                )

            if ended_at < current.linked_at:
                raise PrincipalIdentityLinkTransitionError(
                    "Principal identity link ended_at "
                    "cannot precede linked_at."
                )

            if ended_by_principal_id is not None:
                actor = connection.execute(
                    """
                    SELECT principal_id
                    FROM principals
                    WHERE principal_id = ?
                    """,
                    (ended_by_principal_id,),
                ).fetchone()

                if actor is None:
                    raise (
                        PrincipalIdentityPrincipalNotFoundError(
                            "Ending principal does not "
                            "exist."
                        )
                    )

            cursor = connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    status = 'ended',
                    ended_at = ?,
                    end_reason = ?,
                    ended_by_principal_id = ?
                WHERE
                    link_id = ?
                    AND status = 'active'
                """,
                (
                    ended_at.isoformat(),
                    normalized_reason,
                    ended_by_principal_id,
                    link_id,
                ),
            )

            if cursor.rowcount != 1:
                raise PrincipalIdentityLinkTransitionError(
                    "Principal identity link could "
                    "not be ended."
                )

            stored = self._load_link_from_connection(
                connection,
                link_id,
            )

            if (
                stored.status != "ended"
                or stored.ended_at != ended_at
                or stored.end_reason
                != normalized_reason
                or stored.ended_by_principal_id
                != ended_by_principal_id
            ):
                raise PrincipalIdentityStoreError(
                    "Principal identity link end did "
                    "not produce authoritative state."
                )

            connection.execute("COMMIT")
            return stored

        except (
            PrincipalIdentityStoreError,
            ValueError,
        ):
            self._rollback(connection)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise PrincipalIdentityLinkTransitionError(
                "Principal identity link transition "
                "constraint conflict."
            ) from error
        except sqlite3.Error as error:
            self._rollback(connection)
            raise PrincipalIdentityStoreError(
                "Could not end principal identity "
                "link."
            ) from error
        finally:
            connection.close()

    @staticmethod
    def _load_provider_from_connection(
        connection: sqlite3.Connection,
        identity_provider_id: str,
    ) -> IdentityProvider:
        row = connection.execute(
            """
            SELECT
                identity_provider_id,
                provider_kind,
                issuer,
                status,
                created_at,
                updated_at
            FROM identity_providers
            WHERE identity_provider_id = ?
            """,
            (identity_provider_id,),
        ).fetchone()

        if row is None:
            raise IdentityProviderNotFoundError(
                "Identity provider does not exist."
            )

        return IdentityProvider(
            identity_provider_id=row[
                "identity_provider_id"
            ],
            provider_kind=row["provider_kind"],
            issuer=row["issuer"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _load_link_from_connection(
        connection: sqlite3.Connection,
        link_id: str,
    ) -> PrincipalIdentityLink:
        row = connection.execute(
            """
            SELECT
                link_id,
                identity_provider_id,
                issuer,
                subject,
                principal_id,
                status,
                linked_at,
                ended_at,
                end_reason,
                ended_by_principal_id
            FROM principal_identity_links
            WHERE link_id = ?
            """,
            (link_id,),
        ).fetchone()

        if row is None:
            raise PrincipalIdentityLinkNotFoundError(
                "Principal identity link does not "
                "exist."
            )

        return SQLitePrincipalIdentityStore._link_from_row(
            row
        )

    @staticmethod
    def _link_from_row(
        row: sqlite3.Row,
    ) -> PrincipalIdentityLink:
        return PrincipalIdentityLink(
            link_id=row["link_id"],
            identity_provider_id=row[
                "identity_provider_id"
            ],
            issuer=row["issuer"],
            subject=row["subject"],
            principal_id=row["principal_id"],
            status=row["status"],
            linked_at=row["linked_at"],
            ended_at=row["ended_at"],
            end_reason=row["end_reason"],
            ended_by_principal_id=row[
                "ended_by_principal_id"
            ],
        )

    @staticmethod
    def _raise_link_integrity_error(
        error: sqlite3.IntegrityError,
        *,
        operation: str,
    ) -> NoReturn:
        message = str(error)

        if (
            "External identity is historically "
            "owned by another principal"
            in message
        ):
            raise PrincipalIdentityOwnershipConflictError(
                "External identity is historically "
                "owned by another principal."
            ) from error

        if (
            "UNIQUE constraint failed: "
            "principal_identity_links.issuer, "
            "principal_identity_links.subject"
            in message
        ):
            raise PrincipalIdentityAlreadyLinkedError(
                "External identity already has an "
                "active link."
            ) from error

        raise PrincipalIdentityStoreError(
            f"Could not {operation} principal identity "
            "link."
        ) from error

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
        SQLitePrincipalIdentityStore._validate_exact_value(
            value,
            name=name,
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
