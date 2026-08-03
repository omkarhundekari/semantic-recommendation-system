from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from execution_evidence.current_actor_resolution import (
    CurrentActorResolution,
)
from execution_evidence.current_actor_resolution_service import (
    CurrentActorResolutionService,
)
from execution_evidence.execution_actor_identity_namespace import (
    ExecutionActorIdentityNamespace,
    create_execution_actor_namespace_id,
)
from execution_evidence.execution_actor_identity_namespace_store import (
    ExecutionActorIdentityNamespaceNotFoundError,
    ExecutionActorIdentityNamespaceStoreError,
)
from execution_evidence.execution_event import (
    ExecutionEvent,
    create_execution_event_id,
)
from execution_evidence.principal import (
    Principal,
    create_principal_id,
)
from execution_evidence.principal_identity import (
    IdentityProvider,
    PrincipalIdentityLink,
    create_identity_provider_id,
    create_principal_identity_link_id,
)
from execution_evidence.principal_identity_store import (
    PrincipalIdentityStoreError,
)
from execution_evidence.sqlite_execution_actor_identity_namespace_store import (
    SQLiteExecutionActorIdentityNamespaceStore,
)
from execution_evidence.sqlite_principal_identity_store import (
    SQLitePrincipalIdentityStore,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
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

ISSUER = "github.com"
SUBJECT = "456"


def _principal() -> Principal:
    return Principal(
        principal_id=create_principal_id(),
        principal_kind="human",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _provider() -> IdentityProvider:
    return IdentityProvider(
        identity_provider_id=(
            create_identity_provider_id()
        ),
        provider_kind="github",
        issuer=ISSUER,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _namespace(
    provider: IdentityProvider,
    *,
    source_provider: str = "github",
) -> ExecutionActorIdentityNamespace:
    return ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=(
            create_execution_actor_namespace_id()
        ),
        source_provider=source_provider,
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer=provider.issuer,
        created_at=NOW,
    )


def _link(
    *,
    provider: IdentityProvider,
    principal: Principal,
    subject: str = SUBJECT,
    linked_at: datetime = NOW,
) -> PrincipalIdentityLink:
    return PrincipalIdentityLink(
        link_id=create_principal_identity_link_id(),
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer=provider.issuer,
        subject=subject,
        principal_id=principal.principal_id,
        status="active",
        linked_at=linked_at,
    )


def _event(
    *,
    source_provider: str = "github",
    actor_id: str | None = SUBJECT,
) -> ExecutionEvent:
    return ExecutionEvent(
        execution_event_id=create_execution_event_id(),
        project_id="project-test",
        event_type="test.actor.resolution",
        occurred_at=NOW,
        recorded_at=NOW,
        actor_id=actor_id,
        ingested_by_id="system_test",
        source_provider=source_provider,
        source_account_id=None,
        external_resource_id=None,
        external_entity_type=None,
        external_entity_id=None,
        provider_idempotency_key=(
            "provider:test:"
            + create_execution_event_id()
        ),
        ingestion_method="webhook",
        payload={},
    )


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def _build_resolver(
    database_path: Path,
    *,
    principal: Principal,
    provider: IdentityProvider,
    namespace: ExecutionActorIdentityNamespace,
    link: PrincipalIdentityLink,
) -> CurrentActorResolutionService:
    SQLitePrincipalStore(
        database_path
    ).create(principal)

    identity_store = SQLitePrincipalIdentityStore(
        database_path
    )
    identity_store.create_provider(provider)
    identity_store.create_link(link)

    namespace_store = (
        SQLiteExecutionActorIdentityNamespaceStore(
            database_path
        )
    )
    namespace_store.create(namespace)

    return CurrentActorResolutionService(
        namespace_store=namespace_store,
        principal_identity_store=identity_store,
    )


def test_resolves_current_actor_exactly(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    result = resolver.resolve(_event())

    assert result == CurrentActorResolution(
        principal_id=principal.principal_id,
        identity_link_id=link.link_id,
        execution_actor_namespace_id=(
            namespace.execution_actor_namespace_id
        ),
        issuer=ISSUER,
        subject=SUBJECT,
    )


def test_missing_actor_is_unresolved(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    assert resolver.resolve(
        _event(actor_id=None)
    ) is None


def test_unknown_source_provider_is_unresolved(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    assert resolver.resolve(
        _event(source_provider="gitlab")
    ) is None


@pytest.mark.parametrize(
    "source_provider",
    [
        " github ",
        "GitHub",
    ],
)
def test_source_provider_is_not_normalized(
    database_path: Path,
    source_provider: str,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    assert resolver.resolve(
        _event(source_provider=source_provider)
    ) is None


def test_actor_subject_is_not_normalized(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    assert resolver.resolve(
        _event(actor_id=" 456 ")
    ) is None


def test_unknown_actor_subject_is_unresolved(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    assert resolver.resolve(
        _event(actor_id="999")
    ) is None


def test_ended_link_is_unresolved(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    SQLitePrincipalIdentityStore(
        database_path
    ).end_link(
        link.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    assert resolver.resolve(_event()) is None


def test_same_principal_relink_uses_current_link(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    first_link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=first_link,
    )

    identity_store = SQLitePrincipalIdentityStore(
        database_path
    )

    identity_store.end_link(
        first_link.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    second_link = _link(
        provider=provider,
        principal=principal,
        linked_at=NOW + timedelta(minutes=2),
    )
    identity_store.create_link(second_link)

    result = resolver.resolve(_event())

    assert result is not None
    assert result.principal_id == (
        principal.principal_id
    )
    assert result.identity_link_id == (
        second_link.link_id
    )


def test_resolution_does_not_mutate_event(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()
    namespace = _namespace(provider)
    link = _link(
        provider=provider,
        principal=principal,
    )

    resolver = _build_resolver(
        database_path,
        principal=principal,
        provider=provider,
        namespace=namespace,
        link=link,
    )

    event = _event()
    before = event.model_dump()

    resolver.resolve(event)

    assert event.model_dump() == before


class _RetiredNamespaceStore:
    def __init__(
        self,
        namespace: ExecutionActorIdentityNamespace,
    ) -> None:
        self._namespace = namespace

    def load_current_by_source_provider(
        self,
        source_provider: str,
    ) -> ExecutionActorIdentityNamespace:
        return self._namespace


class _UnusedIdentityStore:
    def load_active_link(
        self,
        *,
        issuer: str,
        subject: str,
    ):
        raise AssertionError(
            "Retired namespace must not reach "
            "identity lookup."
        )


def test_retired_namespace_is_unresolved():
    provider = _provider()

    retired = ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=(
            create_execution_actor_namespace_id()
        ),
        source_provider="github",
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer=provider.issuer,
        created_at=NOW,
        retired_at=NOW + timedelta(minutes=1),
        retired_reason="namespace retired",
    )

    resolver = CurrentActorResolutionService(
        namespace_store=_RetiredNamespaceStore(
            retired
        ),
        principal_identity_store=(
            _UnusedIdentityStore()
        ),
    )

    assert resolver.resolve(_event()) is None


class _FailingNamespaceStore:
    def load_current_by_source_provider(
        self,
        source_provider: str,
    ):
        raise ExecutionActorIdentityNamespaceStoreError(
            "storage unavailable"
        )


def test_namespace_store_failure_propagates():
    resolver = CurrentActorResolutionService(
        namespace_store=_FailingNamespaceStore(),
        principal_identity_store=(
            _UnusedIdentityStore()
        ),
    )

    with pytest.raises(
        ExecutionActorIdentityNamespaceStoreError,
    ):
        resolver.resolve(_event())


class _NamespaceStore:
    def __init__(
        self,
        namespace: ExecutionActorIdentityNamespace,
    ) -> None:
        self._namespace = namespace

    def load_current_by_source_provider(
        self,
        source_provider: str,
    ) -> ExecutionActorIdentityNamespace:
        if (
            source_provider
            != self._namespace.source_provider
        ):
            raise (
                ExecutionActorIdentityNamespaceNotFoundError(
                    "namespace absent"
                )
            )

        return self._namespace


class _FailingIdentityStore:
    def load_active_link(
        self,
        *,
        issuer: str,
        subject: str,
    ):
        raise PrincipalIdentityStoreError(
            "identity storage unavailable"
        )


def test_identity_store_failure_propagates():
    provider = _provider()
    namespace = _namespace(provider)

    resolver = CurrentActorResolutionService(
        namespace_store=_NamespaceStore(
            namespace
        ),
        principal_identity_store=(
            _FailingIdentityStore()
        ),
    )

    with pytest.raises(
        PrincipalIdentityStoreError,
    ):
        resolver.resolve(_event())
