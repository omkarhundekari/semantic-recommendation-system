from __future__ import annotations

import sqlite3
from pathlib import Path

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.request_principal_resolver import (
    RequestPrincipalNotFoundError,
    RequestPrincipalResolutionStoreError,
    RequestPrincipalResolver,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


class SQLiteRequestPrincipalResolver(
    RequestPrincipalResolver
):
    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def resolve(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> AuthenticatedRequestPrincipal:
        if not isinstance(
            identity,
            VerifiedOIDCIdentity,
        ):
            raise TypeError(
                "Request principal resolution requires "
                "a verified OIDC identity."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute("BEGIN")

            try:
                row = connection.execute(
                    """
                    SELECT
                        provider.identity_provider_id,
                        provider.issuer,
                        link.link_id,
                        link.subject,
                        link.principal_id
                    FROM identity_providers AS provider
                    JOIN principal_identity_links AS link
                        ON
                            link.identity_provider_id =
                                provider.identity_provider_id
                            AND link.issuer =
                                provider.issuer
                    JOIN principals AS principal
                        ON
                            principal.principal_id =
                                link.principal_id
                    WHERE
                        provider.identity_provider_id = ?
                        AND provider.issuer = ?
                        AND provider.status = 'active'
                        AND link.subject = ?
                        AND link.status = 'active'
                        AND principal.status = 'active'
                    """,
                    (
                        identity.identity_provider_id,
                        identity.issuer,
                        identity.subject,
                    ),
                ).fetchone()
            finally:
                if connection.in_transaction:
                    connection.rollback()

            if row is None:
                raise RequestPrincipalNotFoundError(
                    "Authenticated request principal "
                    "does not exist or is not active."
                )

            return AuthenticatedRequestPrincipal(
                principal_id=row["principal_id"],
                identity_provider_id=row[
                    "identity_provider_id"
                ],
                identity_link_id=row["link_id"],
                issuer=row["issuer"],
                subject=row["subject"],
            )

        except RequestPrincipalNotFoundError:
            raise
        except sqlite3.Error as error:
            raise RequestPrincipalResolutionStoreError(
                "Could not resolve authenticated "
                "request principal."
            ) from error
        finally:
            connection.close()
