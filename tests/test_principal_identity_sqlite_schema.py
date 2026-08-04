from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import execution_evidence.sqlite_schema as schema
from execution_evidence.principal import (
    create_principal_id,
)
from execution_evidence.sqlite_schema import (
    CURRENT_SQLITE_SCHEMA_VERSION,
    MIGRATIONS,
    apply_execution_evidence_migrations,
    connect_execution_evidence_database,
    get_execution_evidence_schema_version,
    initialize_execution_evidence_database,
)


NOW = "2026-08-02T12:00:00+00:00"
LATER = "2026-08-02T12:01:00+00:00"


def _insert_principal(
    connection,
    principal_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO principals (
            principal_id,
            principal_kind,
            status,
            created_at,
            updated_at
        )
        VALUES (?, 'human', 'active', ?, ?)
        """,
        (
            principal_id,
            NOW,
            NOW,
        ),
    )


def _insert_provider(
    connection,
    *,
    provider_id: str = "idp_test",
    issuer: str = "https://issuer.example",
    status: str = "active",
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
        VALUES (?, 'oidc', ?, ?, ?, ?)
        """,
        (
            provider_id,
            issuer,
            status,
            NOW,
            NOW,
        ),
    )


def _insert_active_link(
    connection,
    *,
    link_id: str,
    provider_id: str,
    issuer: str,
    subject: str,
    principal_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO principal_identity_links (
            link_id,
            identity_provider_id,
            issuer,
            subject,
            principal_id,
            status,
            linked_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (
            link_id,
            provider_id,
            issuer,
            subject,
            principal_id,
            NOW,
        ),
    )


def _end_link(
    connection,
    *,
    link_id: str,
    actor_id: str = None,
) -> None:
    connection.execute(
        """
        UPDATE principal_identity_links
        SET
            status = 'ended',
            ended_at = ?,
            end_reason = 'user unlink',
            ended_by_principal_id = ?
        WHERE link_id = ?
        """,
        (
            LATER,
            actor_id,
            link_id,
        ),
    )


def test_principal_identity_foundation_is_schema_version_17():
    assert CURRENT_SQLITE_SCHEMA_VERSION == 20
    assert MIGRATIONS[16].version == 17
    assert (
        MIGRATIONS[16].name
        == "create_principal_identity_foundation"
    )


def test_fresh_schema_contains_identity_foundation(
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
        tables = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        indexes = {
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            )
            if row["name"] is not None
        }

        user_version = int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    assert version == 20
    assert {
        "identity_providers",
        "principal_identity_links",
    }.issubset(tables)

    assert {
        "idx_principal_identity_links_active",
        "idx_principal_identity_links_identity_history",
        "idx_principal_identity_links_principal_status",
    }.issubset(indexes)

    assert user_version == 20


def test_version_16_upgrades_to_identity_foundation(
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
            MIGRATIONS[:16],
        )
        apply_execution_evidence_migrations(
            connection
        )

        assert (
            get_execution_evidence_schema_version(
                connection
            )
            == 16
        )

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

        assert int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        ) == 17
    finally:
        connection.close()


def test_provider_issuer_is_globally_unique(
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
        _insert_provider(
            connection,
            provider_id="idp_first",
        )

        with pytest.raises(sqlite3.IntegrityError):
            _insert_provider(
                connection,
                provider_id="idp_second",
            )
    finally:
        connection.close()


def test_provider_identity_is_immutable_but_status_can_change(
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
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        connection.execute(
            """
            UPDATE identity_providers
            SET
                status = 'disabled',
                updated_at = ?
            WHERE identity_provider_id = 'idp_test'
            """,
            (LATER,),
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE identity_providers
                SET issuer = 'https://other.example'
                WHERE identity_provider_id = 'idp_test'
                """
            )
    finally:
        connection.close()


def test_provider_delete_is_blocked_without_foreign_keys(
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
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        connection.execute(
            "PRAGMA foreign_keys = OFF"
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM identity_providers
                WHERE identity_provider_id = 'idp_test'
                """
            )
    finally:
        connection.close()


def test_link_requires_matching_provider_issuer_pair(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
            issuer="https://issuer.example",
        )

        with pytest.raises(sqlite3.IntegrityError):
            _insert_active_link(
                connection,
                link_id="pil_bad_pair",
                provider_id="idp_test",
                issuer="https://other.example",
                subject="subject-1",
                principal_id=principal_id,
            )
    finally:
        connection.close()


def test_link_requires_existing_principal(
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
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        with pytest.raises(sqlite3.IntegrityError):
            _insert_active_link(
                connection,
                link_id="pil_missing_principal",
                provider_id="idp_test",
                issuer="https://issuer.example",
                subject="subject-1",
                principal_id=create_principal_id(),
            )
    finally:
        connection.close()


def test_only_one_active_link_per_external_identity(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_first",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        with pytest.raises(sqlite3.IntegrityError):
            _insert_active_link(
                connection,
                link_id="pil_second",
                provider_id="idp_test",
                issuer="https://issuer.example",
                subject="subject-1",
                principal_id=principal_id,
            )
    finally:
        connection.close()


def test_same_principal_can_relink_after_end(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_first",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        _end_link(
            connection,
            link_id="pil_first",
            actor_id=principal_id,
        )

        _insert_active_link(
            connection,
            link_id="pil_second",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        rows = list(
            connection.execute(
                """
                SELECT link_id, status
                FROM principal_identity_links
                WHERE
                    issuer = ?
                    AND subject = ?
                ORDER BY identity_link_row_id
                """,
                (
                    "https://issuer.example",
                    "subject-1",
                ),
            )
        )

        assert len(rows) == 2
        assert rows[0]["status"] == "ended"
        assert rows[1]["status"] == "active"
    finally:
        connection.close()


def test_historical_identity_cannot_move_to_other_principal(
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
        first_principal = create_principal_id()
        second_principal = create_principal_id()

        _insert_principal(
            connection,
            first_principal,
        )
        _insert_principal(
            connection,
            second_principal,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_first",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=first_principal,
        )

        _end_link(
            connection,
            link_id="pil_first",
            actor_id=first_principal,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="historically owned",
        ):
            _insert_active_link(
                connection,
                link_id="pil_second",
                provider_id="idp_test",
                issuer="https://issuer.example",
                subject="subject-1",
                principal_id=second_principal,
            )
    finally:
        connection.close()


def test_link_must_begin_active_without_termination_metadata(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="must begin active",
        ):
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
                    end_reason
                )
                VALUES (?, ?, ?, ?, ?, 'ended', ?, ?, ?)
                """,
                (
                    "pil_invalid",
                    "idp_test",
                    "https://issuer.example",
                    "subject-1",
                    principal_id,
                    NOW,
                    LATER,
                    "invalid genesis",
                ),
            )
    finally:
        connection.close()


def test_active_link_can_end_once(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_test",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        _end_link(
            connection,
            link_id="pil_test",
            actor_id=principal_id,
        )

        stored = connection.execute(
            """
            SELECT
                status,
                ended_at,
                end_reason,
                ended_by_principal_id
            FROM principal_identity_links
            WHERE link_id = 'pil_test'
            """
        ).fetchone()

        assert stored is not None
        assert stored["status"] == "ended"
        assert stored["ended_at"] == LATER
        assert stored["end_reason"] == "user unlink"
        assert (
            stored["ended_by_principal_id"]
            == principal_id
        )
    finally:
        connection.close()


def test_ended_link_is_terminal(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_test",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )
        _end_link(
            connection,
            link_id="pil_test",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET status = 'active'
                WHERE link_id = 'pil_test'
                """
            )
    finally:
        connection.close()


def test_link_identity_fields_are_immutable(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_test",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET subject = 'subject-2'
                WHERE link_id = 'pil_test'
                """
            )
    finally:
        connection.close()


def test_link_delete_is_blocked_without_foreign_keys(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )
        _insert_active_link(
            connection,
            link_id="pil_test",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        connection.execute(
            "PRAGMA foreign_keys = OFF"
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="cannot be deleted",
        ):
            connection.execute(
                """
                DELETE FROM principal_identity_links
                WHERE link_id = 'pil_test'
                """
            )
    finally:
        connection.close()


def test_severing_is_reserved_but_not_reachable_in_v17(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_test",
        )

        _insert_active_link(
            connection,
            link_id="pil_test",
            provider_id="idp_test",
            issuer="https://issuer.example",
            subject="subject-1",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="may only end",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    status = 'ended',
                    ended_at = ?,
                    end_reason = 'administrative unlink',
                    severed_at = ?,
                    severed_reason = 'reserved'
                WHERE link_id = 'pil_test'
                """,
                (
                    LATER,
                    LATER,
                ),
            )

        _end_link(
            connection,
            link_id="pil_test",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    severed_at = ?,
                    severed_reason = 'reserved'
                WHERE link_id = 'pil_test'
                """,
                (LATER,),
            )
    finally:
        connection.close()


def test_active_link_rejects_partial_termination_metadata(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_partial_end",
        )
        _insert_active_link(
            connection,
            link_id="pil_partial_end",
            provider_id="idp_partial_end",
            issuer="https://issuer.example",
            subject="subject-partial",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="may only end",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET ended_at = ?
                WHERE link_id = ?
                """,
                (
                    LATER,
                    "pil_partial_end",
                ),
            )

        stored = connection.execute(
            """
            SELECT
                status,
                ended_at,
                end_reason
            FROM principal_identity_links
            WHERE link_id = ?
            """,
            ("pil_partial_end",),
        ).fetchone()

        assert stored is not None
        assert stored["status"] == "active"
        assert stored["ended_at"] is None
        assert stored["end_reason"] is None
    finally:
        connection.close()


def test_ended_link_termination_metadata_is_immutable(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_terminal_metadata",
        )
        _insert_active_link(
            connection,
            link_id="pil_terminal_metadata",
            provider_id="idp_terminal_metadata",
            issuer="https://issuer.example",
            subject="subject-terminal",
            principal_id=principal_id,
        )

        _end_link(
            connection,
            link_id="pil_terminal_metadata",
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="terminal",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET end_reason = ?
                WHERE link_id = ?
                """,
                (
                    "rewritten reason",
                    "pil_terminal_metadata",
                ),
            )

        stored = connection.execute(
            """
            SELECT
                status,
                ended_at,
                end_reason
            FROM principal_identity_links
            WHERE link_id = ?
            """,
            ("pil_terminal_metadata",),
        ).fetchone()

        assert stored is not None
        assert stored["status"] == "ended"
        assert stored["ended_at"] == LATER
        assert stored["end_reason"] != (
            "rewritten reason"
        )
    finally:
        connection.close()


def test_end_transition_cannot_mutate_identity_fields(
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
        principal_id = create_principal_id()
        _insert_principal(
            connection,
            principal_id,
        )
        _insert_provider(
            connection,
            provider_id="idp_atomic_identity",
        )
        _insert_active_link(
            connection,
            link_id="pil_atomic_identity",
            provider_id="idp_atomic_identity",
            issuer="https://issuer.example",
            subject="subject-original",
            principal_id=principal_id,
        )

        with pytest.raises(
            sqlite3.IntegrityError,
            match="immutable",
        ):
            connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    subject = 'subject-mutated',
                    status = 'ended',
                    ended_at = ?,
                    end_reason = 'user unlink'
                WHERE link_id = ?
                """,
                (
                    LATER,
                    "pil_atomic_identity",
                ),
            )

        stored = connection.execute(
            """
            SELECT
                subject,
                status,
                ended_at,
                end_reason
            FROM principal_identity_links
            WHERE link_id = ?
            """,
            ("pil_atomic_identity",),
        ).fetchone()

        assert stored is not None
        assert stored["subject"] == (
            "subject-original"
        )
        assert stored["status"] == "active"
        assert stored["ended_at"] is None
        assert stored["end_reason"] is None
    finally:
        connection.close()
