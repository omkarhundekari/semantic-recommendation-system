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

from execution_evidence.principal_identity_inspection import (
    PrincipalIdentityInspection,
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


    def inspect(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> PrincipalIdentityInspection:
        """Inspect one verified identity for login provisioning.

        This method is intentionally richer than resolve().

        It is for the login/callback path only.
        Request authentication must continue to use resolve()
        so account state is not exposed through API auth.
        """

        if not isinstance(
            identity,
            VerifiedOIDCIdentity,
        ):
            raise TypeError(
                "Principal inspection requires a "
                "verified OIDC identity."
            )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            provider = connection.execute(
                """
                SELECT
                    identity_provider_id,
                    issuer,
                    status
                FROM identity_providers
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                """,
                (
                    identity.identity_provider_id,
                    identity.issuer,
                ),
            ).fetchone()

            if provider is None:
                return PrincipalIdentityInspection(
                    kind="provider_not_configured"
                )

            if provider["status"] != "active":
                return PrincipalIdentityInspection(
                    kind="provider_disabled"
                )

            link = connection.execute(
                """
                SELECT
                    link_id,
                    principal_id,
                    status
                FROM principal_identity_links
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                    AND subject = ?
                ORDER BY
                    identity_link_row_id DESC
                LIMIT 1
                """,
                (
                    identity.identity_provider_id,
                    identity.issuer,
                    identity.subject,
                ),
            ).fetchone()

            if link is None:
                return PrincipalIdentityInspection(
                    kind="unknown_identity"
                )

            if link["status"] == "ended":
                return PrincipalIdentityInspection(
                    kind="link_ended",
                    principal_id=(
                        str(link["principal_id"])
                    ),
                    identity_link_id=(
                        str(link["link_id"])
                    ),
                )

            principal = connection.execute(
                """
                SELECT
                    principal_id,
                    status
                FROM principals
                WHERE principal_id = ?
                """,
                (link["principal_id"],),
            ).fetchone()

            if principal is None:
                raise (
                    RequestPrincipalResolutionStoreError(
                        "Principal identity link references "
                        "a missing durable principal."
                    )
                )

            if principal["status"] == "suspended":
                return PrincipalIdentityInspection(
                    kind="principal_suspended",
                    principal_id=(
                        str(principal["principal_id"])
                    ),
                    identity_link_id=(
                        str(link["link_id"])
                    ),
                )

            if principal["status"] == "deactivated":
                return PrincipalIdentityInspection(
                    kind="principal_deactivated",
                    principal_id=(
                        str(principal["principal_id"])
                    ),
                    identity_link_id=(
                        str(link["link_id"])
                    ),
                )

            try:
                authenticated = self.resolve(
                    identity
                )
            except RequestPrincipalNotFoundError as error:
                raise (
                    RequestPrincipalResolutionStoreError(
                        "Identity inspection found active "
                        "durable state that resolve() could "
                        "not authenticate."
                    )
                ) from error

            return PrincipalIdentityInspection(
                kind="active",
                principal=authenticated,
                principal_id=(
                    authenticated.principal_id
                ),
                identity_link_id=(
                    authenticated.identity_link_id
                ),
            )

        except RequestPrincipalResolutionStoreError:
            raise
        except Exception as error:
            raise (
                RequestPrincipalResolutionStoreError(
                    "Could not inspect durable request "
                    "principal identity state."
                )
            ) from error
        finally:
            connection.close()

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
