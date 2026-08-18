from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.identity_provider_bootstrap import (
    IdentityProviderBootstrapConflictError,
    IdentityProviderBootstrapService,
    IdentityProviderBootstrapStoreError,
)
from execution_evidence.principal_identity import (
    IdentityProvider,
    create_identity_provider_id,
)
from execution_evidence.sqlite_principal_identity_store import (
    SQLitePrincipalIdentityStore,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    16,
    12,
    0,
    tzinfo=timezone.utc,
)

ISSUER = "https://accounts.google.com"


@pytest.fixture
def database_path(
    tmp_path: Path,
) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _service(
    database_path: Path,
) -> IdentityProviderBootstrapService:
    return IdentityProviderBootstrapService(
        database_path
    )


def test_first_bootstrap_creates_google_provider(
    database_path: Path,
):
    provider_id = create_identity_provider_id()

    result = _service(
        database_path
    ).ensure_google_provider(
        identity_provider_id=provider_id,
        issuer=ISSUER,
        created_at=NOW,
    )

    assert result.created is True
    assert result.provider.identity_provider_id == (
        provider_id
    )
    assert result.provider.provider_kind == "google"
    assert result.provider.issuer == ISSUER
    assert result.provider.status == "active"

    stored = SQLitePrincipalIdentityStore(
        database_path
    ).load_provider(provider_id)

    assert stored == result.provider


def test_exact_replay_is_idempotent(
    database_path: Path,
):
    provider_id = create_identity_provider_id()
    service = _service(database_path)

    first = service.ensure_google_provider(
        identity_provider_id=provider_id,
        issuer=ISSUER,
        created_at=NOW,
    )

    replay = service.ensure_google_provider(
        identity_provider_id=provider_id,
        issuer=ISSUER,
        created_at=NOW,
    )

    assert first.created is True
    assert replay.created is False
    assert replay.provider == first.provider

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM identity_providers
            WHERE issuer = ?
            """,
            (ISSUER,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert count == 1


def test_same_issuer_with_different_provider_id_is_conflict(
    database_path: Path,
):
    service = _service(database_path)

    service.ensure_google_provider(
        identity_provider_id=(
            create_identity_provider_id()
        ),
        issuer=ISSUER,
        created_at=NOW,
    )

    with pytest.raises(
        IdentityProviderBootstrapConflictError,
        match="conflicts",
    ):
        service.ensure_google_provider(
            identity_provider_id=(
                create_identity_provider_id()
            ),
            issuer=ISSUER,
            created_at=NOW,
        )


def test_same_provider_id_with_different_issuer_is_conflict(
    database_path: Path,
):
    provider_id = create_identity_provider_id()
    service = _service(database_path)

    service.ensure_google_provider(
        identity_provider_id=provider_id,
        issuer=ISSUER,
        created_at=NOW,
    )

    with pytest.raises(
        IdentityProviderBootstrapConflictError,
        match="conflicts",
    ):
        service.ensure_google_provider(
            identity_provider_id=provider_id,
            issuer="https://other.example",
            created_at=NOW,
        )


def test_bootstrap_does_not_reactivate_disabled_provider(
    database_path: Path,
):
    provider_id = create_identity_provider_id()

    provider = IdentityProvider(
        identity_provider_id=provider_id,
        provider_kind="google",
        issuer=ISSUER,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            UPDATE identity_providers
            SET status = 'disabled'
            WHERE identity_provider_id = ?
            """,
            (provider_id,),
        )
        connection.execute("COMMIT")
    finally:
        connection.close()

    with pytest.raises(
        IdentityProviderBootstrapConflictError,
        match="will not reactivate",
    ):
        _service(
            database_path
        ).ensure_google_provider(
            identity_provider_id=provider_id,
            issuer=ISSUER,
            created_at=NOW,
        )

    stored = SQLitePrincipalIdentityStore(
        database_path
    ).load_provider(provider_id)

    assert stored.status == "disabled"


def test_bootstrap_does_not_initialize_missing_database(
    tmp_path: Path,
):
    path = tmp_path / "missing.db"

    with pytest.raises(
        IdentityProviderBootstrapStoreError,
    ):
        _service(path).ensure_google_provider(
            identity_provider_id=(
                create_identity_provider_id()
            ),
            issuer=ISSUER,
            created_at=NOW,
        )

    connection = (
        connect_execution_evidence_database(path)
    )

    try:
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }
    finally:
        connection.close()

    assert "identity_providers" not in tables
