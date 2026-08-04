from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.request_principal_resolver import (
    RequestPrincipalNotFoundError,
    RequestPrincipalResolutionStoreError,
)
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
    3,
    12,
    0,
    tzinfo=timezone.utc,
)

PRINCIPAL_ID = (
    "prn_123e4567-e89b-42d3-a456-426614174000"
)
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174001"
)
LINK_ID = (
    "pil_123e4567-e89b-42d3-a456-426614174002"
)
ISSUER = "https://issuer.example"
SUBJECT = "subject-123"


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _insert_identity_graph(
    path: Path,
    *,
    provider_status: str = "active",
    principal_status: str = "active",
):
    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

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
            VALUES (?, 'oidc', ?, ?, ?, ?)
            """,
            (
                PROVIDER_ID,
                ISSUER,
                provider_status,
                NOW.isoformat(),
                NOW.isoformat(),
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

        connection.execute("COMMIT")
    finally:
        connection.close()


def _identity(
    *,
    identity_provider_id=PROVIDER_ID,
    issuer=ISSUER,
    subject=SUBJECT,
):
    return VerifiedOIDCIdentity(
        identity_provider_id=identity_provider_id,
        issuer=issuer,
        subject=subject,
    )


def test_verified_identity_is_bound_to_exact_provider(
    database_path: Path,
):
    _insert_identity_graph(database_path)

    resolver = SQLiteRequestPrincipalResolver(
        database_path
    )

    expected = _identity()

    resolved = resolver.resolve(expected)

    assert resolved.identity_provider_id == PROVIDER_ID
    assert (
        resolved.identity_provider_id
        == expected.identity_provider_id
    )

    forged_provider_identity = _identity(
        identity_provider_id=(
            "idp_223e4567-e89b-42d3-a456-426614174000"
        )
    )

    with pytest.raises(
        RequestPrincipalNotFoundError,
        match="does not exist or is not active",
    ):
        resolver.resolve(
            forged_provider_identity
        )


def test_resolves_enabled_provider_active_link_and_principal(
    database_path: Path,
):
    _insert_identity_graph(database_path)

    result = SQLiteRequestPrincipalResolver(
        database_path
    ).resolve(
        _identity()
    )

    assert result.principal_id == PRINCIPAL_ID
    assert (
        result.identity_provider_id
        == PROVIDER_ID
    )
    assert result.identity_link_id == LINK_ID
    assert result.issuer == ISSUER
    assert result.subject == SUBJECT


def test_disabled_provider_fails_closed(
    database_path: Path,
):
    _insert_identity_graph(
        database_path,
        provider_status="disabled",
    )

    with pytest.raises(
        RequestPrincipalNotFoundError
    ):
        SQLiteRequestPrincipalResolver(
            database_path
        ).resolve(
            _identity()
        )


@pytest.mark.parametrize(
    "principal_status",
    [
        "suspended",
        "deactivated",
    ],
)
def test_inactive_principal_fails_closed(
    database_path: Path,
    principal_status: str,
):
    _insert_identity_graph(
        database_path,
        principal_status=principal_status,
    )

    with pytest.raises(
        RequestPrincipalNotFoundError
    ):
        SQLiteRequestPrincipalResolver(
            database_path
        ).resolve(
            _identity()
        )


def test_ended_link_fails_closed(
    database_path: Path,
):
    _insert_identity_graph(database_path)

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            UPDATE principal_identity_links
            SET
                status = 'ended',
                ended_at = ?,
                end_reason = 'signed out'
            WHERE link_id = ?
            """,
            (
                NOW.isoformat(),
                LINK_ID,
            ),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()

    with pytest.raises(
        RequestPrincipalNotFoundError
    ):
        SQLiteRequestPrincipalResolver(
            database_path
        ).resolve(
            _identity()
        )


@pytest.mark.parametrize(
    ("issuer", "subject"),
    [
        ("https://other.example", SUBJECT),
        (ISSUER, "other-subject"),
    ],
)
def test_identity_matching_is_exact(
    database_path: Path,
    issuer: str,
    subject: str,
):
    _insert_identity_graph(database_path)

    with pytest.raises(
        RequestPrincipalNotFoundError
    ):
        SQLiteRequestPrincipalResolver(
            database_path
        ).resolve(
            _identity(
                issuer=issuer,
                subject=subject,
            )
        )


def test_requires_verified_identity_type(
    database_path: Path,
):
    with pytest.raises(
        TypeError,
        match="verified OIDC identity",
    ):
        SQLiteRequestPrincipalResolver(
            database_path
        ).resolve(
            {"issuer": ISSUER, "subject": SUBJECT}
        )


def test_resolver_does_not_initialize_schema(
    tmp_path: Path,
):
    path = tmp_path / "missing.db"

    with pytest.raises(
        RequestPrincipalResolutionStoreError
    ):
        SQLiteRequestPrincipalResolver(
            path
        ).resolve(
            _identity()
        )
