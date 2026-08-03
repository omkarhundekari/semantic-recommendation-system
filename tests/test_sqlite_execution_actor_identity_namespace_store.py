from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from execution_evidence.execution_actor_identity_namespace import (
    ExecutionActorIdentityNamespace,
    create_execution_actor_namespace_id,
)
from execution_evidence.execution_actor_identity_namespace_store import (
    ExecutionActorIdentityNamespaceAlreadyExistsError,
    ExecutionActorIdentityNamespaceNotFoundError,
    ExecutionActorIdentityNamespaceProviderNotFoundError,
    ExecutionActorIdentityNamespaceStoreError,
    ExecutionActorIdentityNamespaceTransitionError,
)
from execution_evidence.principal_identity import (
    IdentityProvider,
    create_identity_provider_id,
)
from execution_evidence.sqlite_execution_actor_identity_namespace_store import (
    SQLiteExecutionActorIdentityNamespaceStore,
)
from execution_evidence.sqlite_principal_identity_store import (
    SQLitePrincipalIdentityStore,
)
from execution_evidence.sqlite_schema import (
    initialize_execution_evidence_database,
)


NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
)


def _provider(
    *,
    issuer: str = "https://issuer.example",
) -> IdentityProvider:
    return IdentityProvider(
        identity_provider_id=(
            create_identity_provider_id()
        ),
        provider_kind="oidc",
        issuer=issuer,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _namespace(
    *,
    provider: IdentityProvider,
    source_provider: str = "github",
    namespace_id: str | None = None,
) -> ExecutionActorIdentityNamespace:
    return ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=(
            namespace_id
            or create_execution_actor_namespace_id()
        ),
        source_provider=source_provider,
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer=provider.issuer,
        created_at=NOW,
    )


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(
        path
    )
    return path


def test_create_and_load_namespace(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    namespace = _namespace(
        provider=provider
    )

    created = store.create(namespace)

    assert created == namespace
    assert store.load(
        namespace.execution_actor_namespace_id
    ) == namespace


def test_create_rejects_retired_namespace(
    database_path: Path,
):
    provider = _provider()

    namespace = ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=(
            create_execution_actor_namespace_id()
        ),
        source_provider="github",
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer=provider.issuer,
        created_at=NOW,
        retired_at=NOW,
        retired_reason="historical retirement",
    )

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceTransitionError,
        match="begin current",
    ):
        store.create(namespace)


def test_create_requires_matching_provider_issuer(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    namespace = ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=(
            create_execution_actor_namespace_id()
        ),
        source_provider="github",
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer="https://other.example",
        created_at=NOW,
    )

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceProviderNotFoundError,
    ):
        store.create(namespace)


def test_create_requires_existing_provider(
    database_path: Path,
):
    provider = _provider()

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceProviderNotFoundError,
    ):
        store.create(
            _namespace(provider=provider)
        )


def test_duplicate_namespace_id_maps_to_domain_error(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    namespace_id = (
        create_execution_actor_namespace_id()
    )

    store.create(
        _namespace(
            provider=provider,
            source_provider="github",
            namespace_id=namespace_id,
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceAlreadyExistsError,
    ):
        store.create(
            _namespace(
                provider=provider,
                source_provider="gitlab",
                namespace_id=namespace_id,
            )
        )


def test_duplicate_source_provider_maps_to_domain_error(
    database_path: Path,
):
    first_provider = _provider(
        issuer="https://issuer-one.example"
    )
    second_provider = _provider(
        issuer="https://issuer-two.example"
    )

    provider_store = SQLitePrincipalIdentityStore(
        database_path
    )
    provider_store.create_provider(first_provider)
    provider_store.create_provider(second_provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    store.create(
        _namespace(
            provider=first_provider,
            source_provider="github",
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceAlreadyExistsError,
    ):
        store.create(
            _namespace(
                provider=second_provider,
                source_provider="github",
            )
        )


def test_load_missing_namespace(
    database_path: Path,
):
    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceNotFoundError,
    ):
        store.load(
            create_execution_actor_namespace_id()
        )


def test_load_current_by_source_provider_is_exact(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    namespace = store.create(
        _namespace(
            provider=provider,
            source_provider="github",
        )
    )

    assert (
        store.load_current_by_source_provider(
            "github"
        )
        == namespace
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceNotFoundError,
    ):
        store.load_current_by_source_provider(
            " github "
        )


def test_source_provider_case_is_not_normalized(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    store.create(
        _namespace(
            provider=provider,
            source_provider="github",
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceNotFoundError,
    ):
        store.load_current_by_source_provider(
            "GitHub"
        )


def test_multiple_source_providers_can_share_provider(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    first = store.create(
        _namespace(
            provider=provider,
            source_provider="github",
        )
    )
    second = store.create(
        _namespace(
            provider=provider,
            source_provider="github-secondary",
        )
    )

    loaded = store.list_for_identity_provider(
        provider.identity_provider_id
    )

    assert loaded == [
        first,
        second,
    ]


def test_list_unknown_provider_is_empty(
    database_path: Path,
):
    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    assert store.list_for_identity_provider(
        create_identity_provider_id()
    ) == []


def test_namespace_integrity_contract_matches_schema(
    database_path: Path,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    first = _namespace(
        provider=provider,
        source_provider="github",
    )
    store.create(first)

    connection = sqlite3.connect(
        str(database_path)
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
        ) as namespace_id_error:
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
                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    first.execution_actor_namespace_id,
                    "gitlab",
                    provider.identity_provider_id,
                    provider.issuer,
                    NOW.isoformat(),
                ),
            )

        assert (
            "UNIQUE constraint failed: "
            "execution_actor_identity_namespaces."
            "execution_actor_namespace_id"
            in str(namespace_id_error.value)
        )

        with pytest.raises(
            sqlite3.IntegrityError,
        ) as source_provider_error:
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
                VALUES (?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    create_execution_actor_namespace_id(),
                    "github",
                    provider.identity_provider_id,
                    provider.issuer,
                    NOW.isoformat(),
                ),
            )

        assert (
            "UNIQUE constraint failed: "
            "execution_actor_identity_namespaces."
            "source_provider"
            in str(source_provider_error.value)
        )
    finally:
        connection.close()


def test_unknown_namespace_integrity_error_is_not_misclassified(
    database_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    provider = _provider()

    SQLitePrincipalIdentityStore(
        database_path
    ).create_provider(provider)

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    original_connect = (
        __import__(
            "execution_evidence."
            "sqlite_execution_actor_identity_namespace_store",
            fromlist=["connect_execution_evidence_database"],
        )
        .connect_execution_evidence_database
    )

    class FailingConnection:
        def __init__(self, connection):
            self._connection = connection

        @property
        def in_transaction(self):
            return self._connection.in_transaction

        def execute(self, sql, parameters=()):
            normalized = " ".join(sql.split())

            if normalized.startswith(
                "INSERT INTO "
                "execution_actor_identity_namespaces"
            ):
                raise sqlite3.IntegrityError(
                    "CHECK constraint failed: synthetic"
                )

            return self._connection.execute(
                sql,
                parameters,
            )

        def close(self):
            self._connection.close()

    def connect_with_unknown_integrity_error(path):
        return FailingConnection(
            original_connect(path)
        )

    module = __import__(
        "execution_evidence."
        "sqlite_execution_actor_identity_namespace_store",
        fromlist=["connect_execution_evidence_database"],
    )

    monkeypatch.setattr(
        module,
        "connect_execution_evidence_database",
        connect_with_unknown_integrity_error,
    )

    namespace = _namespace(
        provider=provider,
        source_provider="github",
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceStoreError,
    ) as raised:
        store.create(namespace)

    assert not isinstance(
        raised.value,
        ExecutionActorIdentityNamespaceAlreadyExistsError,
    )


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "missing.db"

    store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceStoreError,
    ):
        store.load_current_by_source_provider(
            "github"
        )
