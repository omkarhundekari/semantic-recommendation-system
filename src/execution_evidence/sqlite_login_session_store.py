from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from execution_evidence.login_session import (
    IssuedLoginSession,
    LoginSession,
    MAX_LOGIN_SESSION_TOKEN_BYTES,
    MIN_LOGIN_SESSION_TOKEN_BYTES,
    create_login_session_id,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)


DEFAULT_LOGIN_SESSION_TTL = timedelta(
    days=7
)

MAX_LOGIN_SESSION_TTL = timedelta(
    days=30
)


class LoginSessionStoreError(RuntimeError):
    pass


class LoginSessionNotFoundError(
    LoginSessionStoreError
):
    """Session is missing, expired, revoked, or no longer valid."""


class LoginSessionCreationDeniedError(
    LoginSessionStoreError
):
    """The principal/identity binding cannot create a session."""


class LoginSessionTransitionError(
    LoginSessionStoreError
):
    pass



class LoginTransactionAlreadyConsumedError(
    LoginSessionStoreError
):
    """One interactive-login transaction is single-use."""

    pass


class SQLiteLoginSessionStore:
    """Durable opaque login-session authority.

    Raw session credentials are never stored.

    Reads are intentionally read-only. Session validity
    depends on all of:

    - session has not expired;
    - session has not been revoked;
    - principal is active;
    - bound principal identity link is still active;
    - the identity link still belongs to that principal.
    """

    def __init__(
        self,
        path: Path | str,
    ) -> None:
        self._path = Path(path)

    def create_session(
        self,
        *,
        principal_id: str,
        identity_link_id: str,
        now: datetime,
        ttl: timedelta = DEFAULT_LOGIN_SESSION_TTL,
    ) -> IssuedLoginSession:
        """Create a session outside interactive-login replay scope.

        Interactive Google login must use
        create_session_for_login_transaction() instead.
        """

        return self._create_session(
            principal_id=principal_id,
            identity_link_id=identity_link_id,
            now=now,
            ttl=ttl,
            transaction_id=None,
        )

    def create_session_for_login_transaction(
        self,
        *,
        transaction_id: str,
        principal_id: str,
        identity_link_id: str,
        now: datetime,
        ttl: timedelta = DEFAULT_LOGIN_SESSION_TTL,
    ) -> IssuedLoginSession:
        """Atomically consume one login transaction and issue session.

        The transaction ID and session insert commit together.

        Therefore:

        - replay cannot mint another session;
        - session failure does not burn the transaction;
        - no separate "mark consumed" operation exists.
        """

        transaction_id = self._validate_exact_text(
            transaction_id,
            name="transaction_id",
        )

        if len(
            transaction_id.encode("utf-8")
        ) < 32:
            raise ValueError(
                "transaction_id must contain at least "
                "32 bytes."
            )

        return self._create_session(
            principal_id=principal_id,
            identity_link_id=identity_link_id,
            now=now,
            ttl=ttl,
            transaction_id=transaction_id,
        )

    def _create_session(
        self,
        *,
        principal_id: str,
        identity_link_id: str,
        now: datetime,
        ttl: timedelta,
        transaction_id,
    ) -> IssuedLoginSession:
        normalized_now = self._normalize_time(
            now
        )

        if (
            not isinstance(ttl, timedelta)
            or ttl <= timedelta(0)
            or ttl > MAX_LOGIN_SESSION_TTL
        ):
            raise ValueError(
                "Login session TTL must be greater "
                "than zero and no more than 30 days."
            )

        self._validate_identifier(
            principal_id,
            name="principal_id",
        )
        self._validate_identifier(
            identity_link_id,
            name="identity_link_id",
        )

        expires_at = normalized_now + ttl

        raw_token = secrets.token_urlsafe(
            MIN_LOGIN_SESSION_TOKEN_BYTES
        )

        self._validate_raw_token(raw_token)

        token_hash = self._hash_token(
            raw_token
        )

        session_id = create_login_session_id()

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            binding = connection.execute(
                """
                SELECT
                    p.principal_id,
                    p.status AS principal_status,
                    l.link_id,
                    l.status AS link_status
                FROM principals AS p
                JOIN principal_identity_links AS l
                  ON l.principal_id = p.principal_id
                WHERE
                    p.principal_id = ?
                    AND l.link_id = ?
                """,
                (
                    principal_id,
                    identity_link_id,
                ),
            ).fetchone()

            if (
                binding is None
                or binding["principal_status"]
                    != "active"
                or binding["link_status"]
                    != "active"
            ):
                connection.execute(
                    "ROLLBACK"
                )
                raise (
                    LoginSessionCreationDeniedError(
                        "Login session identity binding "
                        "is not active."
                    )
                )

            connection.execute(
                """
                INSERT INTO login_sessions (
                    session_id,
                    token_hash,
                    principal_id,
                    identity_link_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    revoke_reason
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    NULL,
                    NULL
                )
                """,
                (
                    session_id,
                    token_hash,
                    principal_id,
                    identity_link_id,
                    normalized_now.isoformat(),
                    expires_at.isoformat(),
                ),
            )

            if transaction_id is not None:
                try:
                    connection.execute(
                        """
                        INSERT INTO consumed_login_transactions (
                            transaction_id,
                            session_id,
                            consumed_at
                        )
                        VALUES (
                            ?,
                            ?,
                            ?
                        )
                        """,
                        (
                            transaction_id,
                            session_id,
                            normalized_now.isoformat(),
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    message = str(error)

                    if (
                        "consumed_login_transactions."
                        "transaction_id"
                        in message
                    ):
                        raise (
                            LoginTransactionAlreadyConsumedError(
                                "Login transaction has already "
                                "been consumed."
                            )
                        ) from error

                    raise

            connection.execute(
                "COMMIT"
            )

        except LoginSessionStoreError:
            self._rollback(connection)
            raise

        except sqlite3.IntegrityError as error:
            self._rollback(connection)

            raise LoginSessionStoreError(
                "Login session durable constraint "
                "failure."
            ) from error

        except sqlite3.Error as error:
            self._rollback(connection)

            raise LoginSessionStoreError(
                "Login session storage is "
                "temporarily unavailable."
            ) from error

        finally:
            connection.close()

        return IssuedLoginSession(
            token=raw_token,
            session=LoginSession(
                session_id=session_id,
                principal_id=principal_id,
                identity_link_id=identity_link_id,
                created_at=normalized_now,
                expires_at=expires_at,
                revoked_at=None,
                revoke_reason=None,
            ),
        )

    def resolve_session(
        self,
        token: str,
        *,
        now: datetime,
    ) -> LoginSession:
        self._validate_raw_token(token)

        normalized_now = self._normalize_time(
            now
        )

        token_hash = self._hash_token(
            token
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
                    s.session_id,
                    s.principal_id,
                    s.identity_link_id,
                    s.created_at,
                    s.expires_at,
                    s.revoked_at,
                    s.revoke_reason
                FROM login_sessions AS s
                JOIN principals AS p
                  ON p.principal_id = s.principal_id
                JOIN principal_identity_links AS l
                  ON l.link_id = s.identity_link_id
                 AND l.principal_id = s.principal_id
                WHERE
                    s.token_hash = ?
                    AND s.revoked_at IS NULL
                    AND julianday(s.expires_at)
                        > julianday(?)
                    AND p.status = 'active'
                    AND l.status = 'active'
                LIMIT 1
                """,
                (
                    token_hash,
                    normalized_now.isoformat(),
                ),
            ).fetchone()

        except sqlite3.Error as error:
            raise LoginSessionStoreError(
                "Login session storage is "
                "temporarily unavailable."
            ) from error

        finally:
            connection.close()

        if row is None:
            # Deliberately collapse absent, expired,
            # revoked, inactive-principal, and ended-link
            # states at this boundary.
            raise LoginSessionNotFoundError(
                "Login session is not active."
            )

        return self._session_from_row(
            row
        )

    def revoke_session(
        self,
        token: str,
        *,
        now: datetime,
        reason: str,
    ) -> LoginSession:
        self._validate_raw_token(token)

        normalized_now = self._normalize_time(
            now
        )

        normalized_reason = (
            self._validate_exact_text(
                reason,
                name="reason",
            )
        )

        token_hash = self._hash_token(
            token
        )

        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT
                    session_id,
                    principal_id,
                    identity_link_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    revoke_reason
                FROM login_sessions
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()

            if row is None:
                connection.execute(
                    "ROLLBACK"
                )
                raise LoginSessionNotFoundError(
                    "Login session does not exist."
                )

            current = self._session_from_row(
                row
            )

            if current.revoked_at is not None:
                connection.execute(
                    "ROLLBACK"
                )
                raise LoginSessionTransitionError(
                    "Login session is already revoked."
                )

            if normalized_now < current.created_at:
                connection.execute(
                    "ROLLBACK"
                )
                raise LoginSessionTransitionError(
                    "Login session revocation cannot "
                    "precede creation."
                )

            cursor = connection.execute(
                """
                UPDATE login_sessions
                SET
                    revoked_at = ?,
                    revoke_reason = ?
                WHERE
                    token_hash = ?
                    AND revoked_at IS NULL
                """,
                (
                    normalized_now.isoformat(),
                    normalized_reason,
                    token_hash,
                ),
            )

            if cursor.rowcount != 1:
                raise LoginSessionTransitionError(
                    "Login session could not be revoked."
                )

            stored = connection.execute(
                """
                SELECT
                    session_id,
                    principal_id,
                    identity_link_id,
                    created_at,
                    expires_at,
                    revoked_at,
                    revoke_reason
                FROM login_sessions
                WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()

            if stored is None:
                raise LoginSessionStoreError(
                    "Revoked login session could not "
                    "be reloaded."
                )

            result = self._session_from_row(
                stored
            )

            connection.execute(
                "COMMIT"
            )

            return result

        except LoginSessionStoreError:
            self._rollback(connection)
            raise

        except sqlite3.IntegrityError as error:
            self._rollback(connection)
            raise LoginSessionTransitionError(
                "Login session transition constraint "
                "conflict."
            ) from error

        except sqlite3.Error as error:
            self._rollback(connection)
            raise LoginSessionStoreError(
                "Login session storage is "
                "temporarily unavailable."
            ) from error

        finally:
            connection.close()

    @staticmethod
    def _session_from_row(
        row: sqlite3.Row,
    ) -> LoginSession:
        return LoginSession(
            session_id=row["session_id"],
            principal_id=row["principal_id"],
            identity_link_id=row[
                "identity_link_id"
            ],
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            expires_at=datetime.fromisoformat(
                row["expires_at"]
            ),
            revoked_at=(
                datetime.fromisoformat(
                    row["revoked_at"]
                )
                if row["revoked_at"]
                is not None
                else None
            ),
            revoke_reason=row[
                "revoke_reason"
            ],
        )

    @staticmethod
    def _hash_token(
        token: str,
    ) -> str:
        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

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
                "Login session token is invalid."
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
                "Login session token is invalid."
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
                "Login session timestamp must be "
                "timezone-aware."
            )

        return value.astimezone(
            timezone.utc
        )

    @staticmethod
    def _validate_identifier(
        value: str,
        *,
        name: str,
    ) -> None:
        SQLiteLoginSessionStore._validate_exact_text(
            value,
            name=name,
        )

    @staticmethod
    def _validate_exact_text(
        value: str,
        *,
        name: str,
    ) -> str:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
        ):
            raise ValueError(
                f"{name} must be non-empty exact text."
            )

        return value

    @staticmethod
    def _rollback(
        connection: sqlite3.Connection,
    ) -> None:
        if connection.in_transaction:
            connection.execute(
                "ROLLBACK"
            )
