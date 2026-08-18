from __future__ import annotations

import hashlib
import sqlite3
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from uuid import uuid4

import pytest

from execution_evidence.login_session import (
    LoginSession,
)
from execution_evidence.sqlite_login_session_store import (
    LoginSessionCreationDeniedError,
    LoginSessionNotFoundError,
    LoginSessionTransitionError,
    LoginTransactionAlreadyConsumedError,
    SQLiteLoginSessionStore,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    16,
    22,
    0,
    tzinfo=timezone.utc,
)


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"

    version = (
        initialize_execution_evidence_database(
            path
        )
    )

    assert (
        version
        == CURRENT_SQLITE_SCHEMA_VERSION
        == 28
    )

    return path


def _ids():
    return (
        f"idp_{uuid4()}",
        f"prn_{uuid4()}",
        f"pil_{uuid4()}",
    )


def _seed_active_identity(
    database_path: Path,
):
    (
        provider_id,
        principal_id,
        link_id,
    ) = _ids()

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    timestamp = NOW.isoformat()

    try:
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
            VALUES (
                ?,
                'google',
                ?,
                'active',
                ?,
                ?
            )
            """,
            (
                provider_id,
                "https://accounts.google.com",
                timestamp,
                timestamp,
            ),
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
            VALUES (
                ?,
                'human',
                'active',
                ?,
                ?
            )
            """,
            (
                principal_id,
                timestamp,
                timestamp,
            ),
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
                ?,
                ?,
                ?,
                ?,
                ?,
                'active',
                ?,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL,
                NULL
            )
            """,
            (
                link_id,
                provider_id,
                "https://accounts.google.com",
                "session-test-subject",
                principal_id,
                timestamp,
            ),
        )

    finally:
        connection.close()

    return (
        provider_id,
        principal_id,
        link_id,
    )


def test_schema_version_28_contains_login_sessions(
    database_path: Path,
):
    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 28
        )

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(login_sessions)"
            )
        }

        assert columns == {
            "session_row_id",
            "session_id",
            "token_hash",
            "principal_id",
            "identity_link_id",
            "created_at",
            "expires_at",
            "revoked_at",
            "revoke_reason",
        }

    finally:
        connection.close()


def test_create_session_stores_hash_not_raw_token(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    issued = SQLiteLoginSessionStore(
        database_path
    ).create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    assert isinstance(
        issued.session,
        LoginSession,
    )

    assert (
        issued.session.principal_id
        == principal_id
    )

    assert (
        issued.session.identity_link_id
        == link_id
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT *
            FROM login_sessions
            WHERE session_id = ?
            """,
            (
                issued.session.session_id,
            ),
        ).fetchone()

        assert row is not None

        expected_hash = hashlib.sha256(
            issued.token.encode("utf-8")
        ).hexdigest()

        assert (
            row["token_hash"]
            == expected_hash
        )

        serialized = " ".join(
            str(value)
            for value in row
        )

        assert (
            issued.token
            not in serialized
        )

    finally:
        connection.close()


def test_active_session_resolves_without_writing(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    issued = store.create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        before = tuple(
            connection.execute(
                """
                SELECT *
                FROM login_sessions
                WHERE session_id = ?
                """,
                (
                    issued.session.session_id,
                ),
            ).fetchone()
        )
    finally:
        connection.close()

    resolved = store.resolve_session(
        issued.token,
        now=NOW + timedelta(minutes=5),
    )

    assert (
        resolved
        == issued.session
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        after = tuple(
            connection.execute(
                """
                SELECT *
                FROM login_sessions
                WHERE session_id = ?
                """,
                (
                    issued.session.session_id,
                ),
            ).fetchone()
        )
    finally:
        connection.close()

    assert after == before


def test_expired_session_fails_closed(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    issued = store.create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
        ttl=timedelta(minutes=10),
    )

    with pytest.raises(
        LoginSessionNotFoundError
    ):
        store.resolve_session(
            issued.token,
            now=(
                NOW
                + timedelta(minutes=10)
            ),
        )


def test_revoked_session_fails_closed_and_is_terminal(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    issued = store.create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    revoked = store.revoke_session(
        issued.token,
        now=NOW + timedelta(minutes=1),
        reason="logout",
    )

    assert (
        revoked.revoked_at
        == NOW + timedelta(minutes=1)
    )

    assert (
        revoked.revoke_reason
        == "logout"
    )

    with pytest.raises(
        LoginSessionNotFoundError
    ):
        store.resolve_session(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )

    with pytest.raises(
        LoginSessionTransitionError
    ):
        store.revoke_session(
            issued.token,
            now=NOW + timedelta(minutes=3),
            reason="second_logout",
        )


def test_suspended_principal_invalidates_existing_session(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    issued = store.create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            UPDATE principals
            SET
                status = 'suspended',
                updated_at = ?
            WHERE principal_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(minutes=1)
                ).isoformat(),
                principal_id,
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        LoginSessionNotFoundError
    ):
        store.resolve_session(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )


def test_ended_identity_link_invalidates_existing_session(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    issued = store.create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            UPDATE principal_identity_links
            SET
                status = 'ended',
                ended_at = ?,
                end_reason = 'security_test'
            WHERE link_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(minutes=1)
                ).isoformat(),
                link_id,
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        LoginSessionNotFoundError
    ):
        store.resolve_session(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )


def test_session_cannot_bind_link_to_wrong_principal(
    database_path: Path,
):
    (
        _,
        _,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    other_principal_id = (
        f"prn_{uuid4()}"
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO principals (
                principal_id,
                principal_kind,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                'human',
                'active',
                ?,
                ?
            )
            """,
            (
                other_principal_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        LoginSessionCreationDeniedError
    ):
        SQLiteLoginSessionStore(
            database_path
        ).create_session(
            principal_id=(
                other_principal_id
            ),
            identity_link_id=link_id,
            now=NOW,
        )


def test_schema_rejects_direct_wrong_identity_binding(
    database_path: Path,
):
    (
        _,
        _,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    other_principal_id = (
        f"prn_{uuid4()}"
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            INSERT INTO principals (
                principal_id,
                principal_kind,
                status,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                'human',
                'active',
                ?,
                ?
            )
            """,
            (
                other_principal_id,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match=(
                "identity binding is not active"
            ),
        ):
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
                    f"ses_{uuid4()}",
                    "a" * 64,
                    other_principal_id,
                    link_id,
                    NOW.isoformat(),
                    (
                        NOW
                        + timedelta(hours=1)
                    ).isoformat(),
                ),
            )

    finally:
        connection.close()


def test_session_identity_fields_are_immutable(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    issued = SQLiteLoginSessionStore(
        database_path
    ).create_session(
        principal_id=principal_id,
        identity_link_id=link_id,
        now=NOW,
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="identity fields are immutable",
        ):
            connection.execute(
                """
                UPDATE login_sessions
                SET expires_at = ?
                WHERE session_id = ?
                """,
                (
                    (
                        NOW
                        + timedelta(days=20)
                    ).isoformat(),
                    issued.session.session_id,
                ),
            )

    finally:
        connection.close()



def test_login_transaction_is_single_use(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    transaction_id = (
        "transaction-"
        "0123456789abcdef0123456789abcdef"
    )

    first = (
        store
        .create_session_for_login_transaction(
            transaction_id=transaction_id,
            principal_id=principal_id,
            identity_link_id=link_id,
            now=NOW,
        )
    )

    with pytest.raises(
        LoginTransactionAlreadyConsumedError
    ):
        (
            store
            .create_session_for_login_transaction(
                transaction_id=transaction_id,
                principal_id=principal_id,
                identity_link_id=link_id,
                now=NOW + timedelta(seconds=1),
            )
        )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        sessions = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM login_sessions
            """
        ).fetchone()

        consumed = connection.execute(
            """
            SELECT
                transaction_id,
                session_id
            FROM consumed_login_transactions
            """
        ).fetchall()

        assert sessions["count"] == 1

        assert len(consumed) == 1

        assert (
            consumed[0]["transaction_id"]
            == transaction_id
        )

        assert (
            consumed[0]["session_id"]
            == first.session.session_id
        )

    finally:
        connection.close()


def test_failed_session_insert_does_not_consume_transaction(
    database_path: Path,
):
    (
        _,
        principal_id,
        link_id,
    ) = _seed_active_identity(
        database_path
    )

    transaction_id = (
        "transaction-"
        "fedcba9876543210fedcba9876543210"
    )

    store = SQLiteLoginSessionStore(
        database_path
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute(
            """
            UPDATE principals
            SET
                status = 'suspended',
                updated_at = ?
            WHERE principal_id = ?
            """,
            (
                (
                    NOW
                    + timedelta(seconds=1)
                ).isoformat(),
                principal_id,
            ),
        )
    finally:
        connection.close()

    with pytest.raises(
        LoginSessionCreationDeniedError
    ):
        (
            store
            .create_session_for_login_transaction(
                transaction_id=transaction_id,
                principal_id=principal_id,
                identity_link_id=link_id,
                now=NOW + timedelta(seconds=2),
            )
        )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT transaction_id
            FROM consumed_login_transactions
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()

        assert row is None

    finally:
        connection.close()
