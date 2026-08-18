from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.login_session import (
    MAX_LOGIN_SESSION_TOKEN_BYTES,
    MIN_LOGIN_SESSION_TOKEN_BYTES,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


class SessionAuthenticatedPrincipalError(
    RuntimeError
):
    pass


class SessionAuthenticatedPrincipalNotFoundError(
    SessionAuthenticatedPrincipalError
):
    """Session does not authenticate an active principal."""


class SessionAuthenticatedPrincipalStoreError(
    SessionAuthenticatedPrincipalError
):
    """Durable session/principal state cannot be read."""


class SQLiteSessionAuthenticatedPrincipalResolver:
    """Resolve one opaque login session directly to principal authority.

    This is deliberately separate from RequestAuthenticator.

    Bearer credentials remain owned by RequestAuthenticator.
    Browser-session credentials are owned by this resolver.

    Both paths converge only after authentication by returning
    the same AuthenticatedRequestPrincipal domain type.

    Resolution is read-only and requires all of:

    - session exists;
    - session is not revoked;
    - session is not expired;
    - principal remains active;
    - identity link remains active;
    - identity link still belongs to the session principal;
    - identity provider remains active.
    """

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
        token: str,
        *,
        now: datetime,
    ) -> AuthenticatedRequestPrincipal:
        self._validate_raw_token(
            token
        )

        normalized_now = (
            self._normalize_time(
                now
            )
        )

        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

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
                        session.principal_id,
                        link.identity_provider_id,
                        link.link_id,
                        link.issuer,
                        link.subject
                    FROM login_sessions AS session

                    JOIN principal_identity_links AS link
                      ON
                        link.link_id =
                            session.identity_link_id
                        AND link.principal_id =
                            session.principal_id

                    JOIN principals AS principal
                      ON
                        principal.principal_id =
                            session.principal_id

                    JOIN identity_providers AS provider
                      ON
                        provider.identity_provider_id =
                            link.identity_provider_id
                        AND provider.issuer =
                            link.issuer

                    WHERE
                        session.token_hash = ?
                        AND session.revoked_at IS NULL
                        AND julianday(session.expires_at)
                            > julianday(?)
                        AND principal.status = 'active'
                        AND link.status = 'active'
                        AND provider.status = 'active'
                    """,
                    (
                        token_hash,
                        normalized_now.isoformat(),
                    ),
                ).fetchone()

            finally:
                if connection.in_transaction:
                    connection.rollback()

            if row is None:
                # Missing, expired, revoked, suspended,
                # deactivated, ended-link, provider-disabled,
                # or mismatched durable identity states are
                # deliberately indistinguishable.
                raise (
                    SessionAuthenticatedPrincipalNotFoundError(
                        "Browser session does not authenticate "
                        "an active principal."
                    )
                )

            return AuthenticatedRequestPrincipal(
                principal_id=row[
                    "principal_id"
                ],
                identity_provider_id=row[
                    "identity_provider_id"
                ],
                identity_link_id=row[
                    "link_id"
                ],
                issuer=row[
                    "issuer"
                ],
                subject=row[
                    "subject"
                ],
            )

        except SessionAuthenticatedPrincipalNotFoundError:
            raise

        except sqlite3.Error as error:
            raise (
                SessionAuthenticatedPrincipalStoreError(
                    "Browser-session principal resolution "
                    "is temporarily unavailable."
                )
            ) from error

        finally:
            connection.close()

    @staticmethod
    def _validate_raw_token(
        token: str,
    ) -> None:
        if (
            not isinstance(token, str)
            or not token
            or token != token.strip()
        ):
            raise ValueError(
                "Browser session token is invalid."
            )

        encoded = token.encode(
            "utf-8"
        )

        if (
            len(encoded)
            < MIN_LOGIN_SESSION_TOKEN_BYTES
            or len(encoded)
            > MAX_LOGIN_SESSION_TOKEN_BYTES
        ):
            raise ValueError(
                "Browser session token is invalid."
            )

    @staticmethod
    def _normalize_time(
        value: datetime,
    ) -> datetime:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Browser-session principal timestamp "
                "must be timezone-aware."
            )

        return value.astimezone(
            timezone.utc
        )
