from __future__ import annotations

from execution_evidence.sqlite_schema import CURRENT_SQLITE_SCHEMA_VERSION
from execution_evidence.sqlite_schema import initialize_execution_evidence_database

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

import pytest
from uuid import uuid4

from execution_evidence.sqlite_login_session_store import (
    SQLiteLoginSessionStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.sqlite_session_authenticated_principal_resolver import (
    SessionAuthenticatedPrincipalNotFoundError,
    SQLiteSessionAuthenticatedPrincipalResolver,
)



NOW = datetime(
    2026,
    8,
    17,
    20,
    0,
    tzinfo=timezone.utc,
)


def test_active_session_resolves_full_authenticated_principal(
    database_path: Path,
):
    (
        provider_id,
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

    principal = (
        SQLiteSessionAuthenticatedPrincipalResolver(
            database_path
        ).resolve(
            issued.token,
            now=NOW + timedelta(minutes=1),
        )
    )

    assert (
        principal.principal_id
        == principal_id
    )

    assert (
        principal.identity_link_id
        == link_id
    )

    assert (
        principal.identity_provider_id
        == provider_id
    )

    assert (
        principal.issuer
        == "https://accounts.google.com"
    )

    assert principal.subject


def test_revoked_session_fails_closed(
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

    store.revoke_session(
        issued.token,
        now=NOW + timedelta(minutes=1),
        reason="logout",
    )

    with pytest.raises(
        SessionAuthenticatedPrincipalNotFoundError
    ):
        SQLiteSessionAuthenticatedPrincipalResolver(
            database_path
        ).resolve(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )


def test_suspended_principal_fails_closed(
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
        SessionAuthenticatedPrincipalNotFoundError
    ):
        SQLiteSessionAuthenticatedPrincipalResolver(
            database_path
        ).resolve(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )


def test_ended_identity_link_fails_closed(
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
        SessionAuthenticatedPrincipalNotFoundError
    ):
        SQLiteSessionAuthenticatedPrincipalResolver(
            database_path
        ).resolve(
            issued.token,
            now=NOW + timedelta(minutes=2),
        )



@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = (
        tmp_path
        / "session-authenticated-principal.db"
    )

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



def _seed_active_identity(
    database_path: Path,
):
    provider_id = (
        f"idp_{uuid4()}"
    )

    principal_id = (
        f"prn_{uuid4()}"
    )

    link_id = (
        f"pil_{uuid4()}"
    )

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    timestamp = (
        NOW.isoformat()
    )

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
                "session-principal-test-subject",
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
