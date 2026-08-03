from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

import pytest
from pydantic import ValidationError

from execution_evidence.principal import (
    Principal,
    create_principal_id,
)
from execution_evidence.principal_store import (
    PrincipalAlreadyExistsError,
    PrincipalKindNotFoundError,
    PrincipalNotFoundError,
    PrincipalStoreError,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    initialize_execution_evidence_database,
)


CREATED_AT = datetime(
    2026,
    8,
    1,
    12,
    0,
    tzinfo=timezone.utc,
)


def _principal(
    *,
    principal_id: Optional[str] = None,
    principal_kind: str = "human",
) -> Principal:
    return Principal(
        principal_id=(
            principal_id
            or create_principal_id()
        ),
        principal_kind=principal_kind,
        status="active",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def test_create_principal_id_is_random_uuid4():
    first = create_principal_id()
    second = create_principal_id()

    assert first != second
    assert first.startswith("prn_")
    assert second.startswith("prn_")

    first_uuid = UUID(
        first.removeprefix("prn_")
    )
    second_uuid = UUID(
        second.removeprefix("prn_")
    )

    assert first_uuid.version == 4
    assert second_uuid.version == 4


def test_principal_rejects_non_uuid4_identity():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        Principal(
            principal_id=(
                "prn_00000000-0000-1000-"
                "8000-000000000001"
            ),
            principal_kind="human",
            status="active",
            created_at=CREATED_AT,
            updated_at=CREATED_AT,
        )


def test_principal_requires_timezone_aware_dates():
    naive = datetime(
        2026,
        8,
        1,
        12,
        0,
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        Principal(
            principal_id=create_principal_id(),
            principal_kind="human",
            status="active",
            created_at=naive,
            updated_at=naive,
        )


def test_store_creates_and_loads_principal(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )
    principal = _principal()

    created = store.create(principal)
    loaded = store.load(
        principal.principal_id
    )

    assert created == principal
    assert loaded == principal


@pytest.mark.parametrize(
    "principal_kind",
    [
        "human",
        "service",
        "system",
        "agent",
    ],
)
def test_seeded_principal_kinds_are_accepted(
    tmp_path: Path,
    principal_kind: str,
):
    database_path = (
        tmp_path
        / f"{principal_kind}.db"
    )
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )

    created = store.create(
        _principal(
            principal_kind=principal_kind
        )
    )

    assert (
        created.principal_kind
        == principal_kind
    )


def test_store_rejects_unregistered_kind(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )

    with pytest.raises(
        PrincipalKindNotFoundError,
        match="not registered",
    ):
        store.create(
            _principal(
                principal_kind=(
                    "future_kind"
                )
            )
        )


def test_lookup_is_case_sensitive(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )
    principal = _principal()
    store.create(principal)

    case_variant = (
        "prn_"
        + principal.principal_id[
            len("prn_"):
        ].upper()
    )

    with pytest.raises(
        PrincipalNotFoundError,
        match="does not exist",
    ):
        store.load(case_variant)


def test_lookup_rejects_noncanonical_whitespace(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )
    principal = _principal()
    store.create(principal)

    with pytest.raises(
        ValueError,
        match="surrounding whitespace",
    ):
        store.load(
            f" {principal.principal_id} "
        )


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    store = SQLitePrincipalStore(
        database_path
    )

    with pytest.raises(
        PrincipalStoreError,
        match="Could not create principal",
    ):
        store.create(_principal())

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        tables = {
            str(row[0])
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

    assert "principals" not in tables
    assert "principal_kinds" not in tables


def test_lookup_fails_closed_for_unknown_principal(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )

    with pytest.raises(
        PrincipalNotFoundError,
        match="does not exist",
    ):
        store.load(
            create_principal_id()
        )


def test_duplicate_principal_is_rejected(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    store = SQLitePrincipalStore(
        database_path
    )
    principal = _principal()

    store.create(principal)

    with pytest.raises(
        PrincipalAlreadyExistsError,
        match="already exists",
    ):
        store.create(principal)


def test_database_restricts_unknown_kind(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO principals (
                    principal_id,
                    principal_kind,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    create_principal_id(),
                    "unknown",
                    "active",
                    CREATED_AT.isoformat(),
                    CREATED_AT.isoformat(),
                ),
            )
    finally:
        connection.close()


def test_database_restricts_invalid_status(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        database_path
    )

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        with pytest.raises(
            sqlite3.IntegrityError
        ):
            connection.execute(
                """
                INSERT INTO principals (
                    principal_id,
                    principal_kind,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    create_principal_id(),
                    "human",
                    "deleted",
                    CREATED_AT.isoformat(),
                    CREATED_AT.isoformat(),
                ),
            )
    finally:
        connection.close()
