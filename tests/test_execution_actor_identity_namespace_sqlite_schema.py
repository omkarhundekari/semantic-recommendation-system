from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

import execution_evidence.sqlite_schema as schema
from execution_evidence.principal_identity import (
    create_identity_provider_id,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MIGRATIONS,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
).isoformat()

ISSUER = "https://issuer.example"


def _insert_provider(
    connection: sqlite3.Connection,
    *,
    provider_id: str,
    issuer: str = ISSUER,
) -> None:
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
        VALUES (?, 'oidc', ?, 'active', ?, ?)
        """,
        (
            provider_id,
            issuer,
            NOW,
            NOW,
        ),
    )


def _insert_namespace(
    connection: sqlite3.Connection,
    *,
    namespace_id: str,
    source_provider: str,
    provider_id: str,
    issuer: str = ISSUER,
) -> None:
    connection.execute(
        """
        INSERT INTO execution_actor_identity_namespaces (
            execution_actor_namespace_id,
            source_provider,
            identity_provider_id,
            issuer,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            namespace_id,
            source_provider,
            provider_id,
            issuer,
            NOW,
        ),
    )


def test_namespace_foundation_is_schema_version_18():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 20
    assert MIGRATIONS[17].version == 18
    assert (
        MIGRATIONS[17].name
        == "create_execution_actor_identity_namespace"
    )


def test_fresh_schema_contains_namespace_foundation(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    version = initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE
                type = 'table'
                AND name = ?
            """,
            (
                "execution_actor_identity_namespaces",
            ),
        ).fetchone()

        triggers = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'trigger'
                """
            )
        }

        user_version = int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert version == 20
    assert table is not None
    assert (
        "prevent_execution_actor_namespace_update"
        in triggers
    )
    assert (
        "prevent_execution_actor_namespace_delete"
        in triggers
    )
    assert user_version == 20


def test_version_17_upgrades_to_namespace_foundation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    database_path = tmp_path / "solvyn.db"

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS[:17],
        )

        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 17
        )

        monkeypatch.setattr(
            schema,
            "MIGRATIONS",
            MIGRATIONS[:18],
        )

        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 18
        )

        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 18
    finally:
        connection.close()


def test_namespace_requires_matching_provider_issuer_pair(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="FOREIGN KEY",
        ):
            _insert_namespace(
                connection,
                namespace_id="ean_test",
                source_provider="github",
                provider_id=provider_id,
                issuer="https://other.example",
            )
    finally:
        connection.close()


def test_source_provider_is_globally_unique_for_all_history(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        first_provider = create_identity_provider_id()
        second_provider = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=first_provider,
            issuer="https://issuer-one.example",
        )
        _insert_provider(
            connection,
            provider_id=second_provider,
            issuer="https://issuer-two.example",
        )

        _insert_namespace(
            connection,
            namespace_id="ean_first",
            source_provider="github",
            provider_id=first_provider,
            issuer="https://issuer-one.example",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="UNIQUE",
        ):
            _insert_namespace(
                connection,
                namespace_id="ean_second",
                source_provider="github",
                provider_id=second_provider,
                issuer="https://issuer-two.example",
            )
    finally:
        connection.close()


def test_multiple_source_providers_can_share_identity_namespace(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        _insert_namespace(
            connection,
            namespace_id="ean_first",
            source_provider="github",
            provider_id=provider_id,
        )

        _insert_namespace(
            connection,
            namespace_id="ean_second",
            source_provider="github-secondary",
            provider_id=provider_id,
        )

        count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM execution_actor_identity_namespaces
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                """,
                (
                    provider_id,
                    ISSUER,
                ),
            ).fetchone()[0]
        )

        assert count == 2
    finally:
        connection.close()


def test_retirement_fields_must_move_together(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO execution_actor_identity_namespaces (
                    execution_actor_namespace_id,
                    source_provider,
                    identity_provider_id,
                    issuer,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    "ean_invalid",
                    "github",
                    provider_id,
                    ISSUER,
                    NOW,
                    NOW,
                ),
            )
    finally:
        connection.close()


def test_namespace_cannot_begin_retired(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="must begin current",
        ):
            connection.execute(
                """
                INSERT INTO execution_actor_identity_namespaces (
                    execution_actor_namespace_id,
                    source_provider,
                    identity_provider_id,
                    issuer,
                    created_at,
                    retired_at,
                    retired_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "ean_retired_genesis",
                    "github",
                    provider_id,
                    ISSUER,
                    NOW,
                    NOW,
                    "not reachable in v18",
                ),
            )

        count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM execution_actor_identity_namespaces
                WHERE execution_actor_namespace_id = ?
                """,
                ("ean_retired_genesis",),
            ).fetchone()[0]
        )

        assert count == 0
    finally:
        connection.close()


def test_namespace_updates_are_blocked(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        _insert_namespace(
            connection,
            namespace_id="ean_test",
            source_provider="github",
            provider_id=provider_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE execution_actor_identity_namespaces
                SET
                    retired_at = ?,
                    retired_reason = ?
                WHERE execution_actor_namespace_id = ?
                """,
                (
                    NOW,
                    "not reachable in v18",
                    "ean_test",
                ),
            )
    finally:
        connection.close()


def test_namespace_delete_is_blocked_without_foreign_keys(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        provider_id = create_identity_provider_id()

        _insert_provider(
            connection,
            provider_id=provider_id,
        )

        _insert_namespace(
            connection,
            namespace_id="ean_test",
            source_provider="github",
            provider_id=provider_id,
        )

        connection.execute(
            "PRAGMA foreign_keys = OFF"
        )

        assert (
            connection.execute(
                "PRAGMA foreign_keys"
            ).fetchone()[0]
            == 0
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE
                FROM execution_actor_identity_namespaces
                WHERE execution_actor_namespace_id = ?
                """,
                ("ean_test",),
            )

        stored = connection.execute(
            """
            SELECT execution_actor_namespace_id
            FROM execution_actor_identity_namespaces
            WHERE execution_actor_namespace_id = ?
            """,
            ("ean_test",),
        ).fetchone()

        assert stored is not None
    finally:
        connection.close()
