from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.sqlite_request_principal_resolver import (
    SQLiteRequestPrincipalResolver,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


NOW = datetime(
    2026,
    8,
    16,
    12,
    0,
    tzinfo=timezone.utc,
)

PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174111"
)
PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174112"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174113"
)

ISSUER = "https://accounts.google.com"
SUBJECT = "google-user-123"


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def identity() -> VerifiedOIDCIdentity:
    return VerifiedOIDCIdentity(
        identity_provider_id=PROVIDER_ID,
        issuer=ISSUER,
        subject=SUBJECT,
    )


def insert_provider(
    path: Path,
    *,
    status: str = "active",
) -> None:
    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

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
                ?,
                ?,
                ?
            )
            """,
            (
                PROVIDER_ID,
                ISSUER,
                status,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

        connection.execute("COMMIT")
    finally:
        connection.close()


def insert_graph(
    path: Path,
    *,
    principal_status: str = "active",
    link_status: str = "active",
) -> None:
    insert_provider(path)

    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
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
            VALUES (?, 'human', ?, ?, ?)
            """,
            (
                PRINCIPAL_ID,
                principal_status,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

        # Identity links are lifecycle records and must
        # always begin active. Tests that need historical
        # ended/severed state must transition the row after
        # creation rather than inserting an impossible
        # terminal state directly.
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
                ?, ?, ?, ?, ?, 'active', ?,
                NULL, NULL, NULL,
                NULL, NULL, NULL
            )
            """,
            (
                LINK_ID,
                PROVIDER_ID,
                ISSUER,
                SUBJECT,
                PRINCIPAL_ID,
                NOW.isoformat(),
            ),
        )

        if link_status == "ended":
            connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    status = 'ended',
                    ended_at = ?,
                    end_reason = 'ended'
                WHERE link_id = ?
                """,
                (
                    NOW.isoformat(),
                    LINK_ID,
                ),
            )
        elif link_status != "active":
            raise ValueError(
                f"Unsupported test link status: {link_status!r}"
            )

        connection.execute("COMMIT")
    finally:
        connection.close()

def test_provider_not_configured(
    database_path: Path,
):
    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert (
        result.kind
        == "provider_not_configured"
    )


def test_unknown_identity_with_active_provider(
    database_path: Path,
):
    insert_provider(database_path)

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert result.kind == "unknown_identity"


def test_disabled_provider(
    database_path: Path,
):
    insert_provider(
        database_path,
        status="disabled",
    )

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert result.kind == "provider_disabled"


def test_active_identity(
    database_path: Path,
):
    insert_graph(database_path)

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert result.kind == "active"
    assert (
        result.require_active().principal_id
        == PRINCIPAL_ID
    )


@pytest.mark.parametrize(
    ("principal_status", "expected"),
    [
        (
            "suspended",
            "principal_suspended",
        ),
        (
            "deactivated",
            "principal_deactivated",
        ),
    ],
)
def test_inactive_principal_states(
    database_path: Path,
    principal_status: str,
    expected: str,
):
    insert_graph(
        database_path,
        principal_status=principal_status,
    )

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert result.kind == expected


def test_ended_link_is_distinct(
    database_path: Path,
):
    insert_graph(
        database_path,
        link_status="ended",
    )

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).inspect(
        identity()
    )

    assert result.kind == "link_ended"
