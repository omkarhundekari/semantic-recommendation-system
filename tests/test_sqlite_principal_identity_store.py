from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
    IdentityProviderAlreadyExistsError,
    IdentityProviderNotFoundError,
    PrincipalIdentityAlreadyLinkedError,
    PrincipalIdentityLinkNotFoundError,
    PrincipalIdentityLinkTransitionError,
    PrincipalIdentityOwnershipConflictError,
    PrincipalIdentityPrincipalNotFoundError,
    PrincipalIdentityStoreError,
)
from execution_evidence.sqlite_principal_identity_store import (
    SQLitePrincipalIdentityStore,
)
from execution_evidence.sqlite_principal_store import (
    SQLitePrincipalStore,
)
from execution_evidence.sqlite_schema import (
    CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL,
    connect_execution_evidence_database,
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


def _principal(
    *,
    principal_id: str | None = None,
) -> Principal:
    return Principal(
        principal_id=(
            principal_id
            or create_principal_id()
        ),
        principal_kind="human",
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _provider(
    *,
    provider_id: str | None = None,
    issuer: str = "https://issuer.example",
) -> IdentityProvider:
    return IdentityProvider(
        identity_provider_id=(
            provider_id
            or create_identity_provider_id()
        ),
        provider_kind="oidc",
        issuer=issuer,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )


def _link(
    *,
    provider: IdentityProvider,
    principal: Principal,
    subject: str = "subject-1",
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


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "solvyn.db"
    initialize_execution_evidence_database(path)
    return path


def test_create_and_load_provider(
    database_path: Path,
):
    store = SQLitePrincipalIdentityStore(
        database_path
    )
    provider = _provider()

    created = store.create_provider(provider)
    loaded = store.load_provider(
        provider.identity_provider_id
    )

    assert created == provider
    assert loaded == provider


def test_duplicate_provider_id_maps_to_domain_error(
    database_path: Path,
):
    store = SQLitePrincipalIdentityStore(
        database_path
    )
    provider = _provider()

    store.create_provider(provider)

    with pytest.raises(
        IdentityProviderAlreadyExistsError,
    ):
        store.create_provider(provider)


def test_duplicate_provider_issuer_maps_to_domain_error(
    database_path: Path,
):
    store = SQLitePrincipalIdentityStore(
        database_path
    )

    first = _provider()
    second = _provider(
        issuer=first.issuer,
    )

    store.create_provider(first)

    with pytest.raises(
        IdentityProviderAlreadyExistsError,
    ):
        store.create_provider(second)


def test_load_missing_provider(
    database_path: Path,
):
    store = SQLitePrincipalIdentityStore(
        database_path
    )

    with pytest.raises(
        IdentityProviderNotFoundError,
    ):
        store.load_provider(
            create_identity_provider_id()
        )


def test_create_and_load_link(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
    )

    created = store.create_link(link)
    loaded = store.load_link(link.link_id)
    active = store.load_active_link(
        issuer=provider.issuer,
        subject=link.subject,
    )

    assert created == link
    assert loaded == link
    assert active == link


def test_link_requires_matching_provider_issuer(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    mismatched = PrincipalIdentityLink(
        link_id=create_principal_identity_link_id(),
        identity_provider_id=(
            provider.identity_provider_id
        ),
        issuer="https://other.example",
        subject="subject-1",
        principal_id=principal.principal_id,
        status="active",
        linked_at=NOW,
    )

    with pytest.raises(
        IdentityProviderNotFoundError,
    ):
        store.create_link(mismatched)


def test_link_requires_existing_principal(
    database_path: Path,
):
    provider = _provider()
    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    missing = _principal()
    link = _link(
        provider=provider,
        principal=missing,
    )

    with pytest.raises(
        PrincipalIdentityPrincipalNotFoundError,
    ):
        store.create_link(link)


def test_duplicate_active_link_maps_to_domain_error(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    first = _link(
        provider=provider,
        principal=principal,
    )
    second = _link(
        provider=provider,
        principal=principal,
    )

    store.create_link(first)

    with pytest.raises(
        PrincipalIdentityAlreadyLinkedError,
    ):
        store.create_link(second)


def test_historical_ownership_conflict_maps_to_domain_error(
    database_path: Path,
):
    first_principal = _principal()
    second_principal = _principal()
    provider = _provider()

    principal_store = SQLitePrincipalStore(
        database_path
    )
    principal_store.create(first_principal)
    principal_store.create(second_principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    first = _link(
        provider=provider,
        principal=first_principal,
    )
    store.create_link(first)
    store.end_link(
        first.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    conflicting = _link(
        provider=provider,
        principal=second_principal,
        linked_at=NOW + timedelta(minutes=2),
    )

    with pytest.raises(
        PrincipalIdentityOwnershipConflictError,
    ):
        store.create_link(conflicting)


def test_same_principal_can_relink_after_end(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    first = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(first)
    store.end_link(
        first.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    second = _link(
        provider=provider,
        principal=principal,
        linked_at=NOW + timedelta(minutes=2),
    )

    created = store.create_link(second)

    assert created.status == "active"
    assert created.principal_id == (
        principal.principal_id
    )


def test_list_principal_links_preserves_periods(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    first = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(first)
    store.end_link(
        first.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    second = _link(
        provider=provider,
        principal=principal,
        linked_at=NOW + timedelta(minutes=2),
    )
    store.create_link(second)

    links = store.list_principal_links(
        principal.principal_id
    )

    assert [link.link_id for link in links] == [
        first.link_id,
        second.link_id,
    ]
    assert links[0].status == "ended"
    assert links[1].status == "active"


def test_end_link_returns_authoritative_state(
    database_path: Path,
):
    principal = _principal()
    actor = _principal()
    provider = _provider()

    principal_store = SQLitePrincipalStore(
        database_path
    )
    principal_store.create(principal)
    principal_store.create(actor)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(link)

    ended_at = NOW + timedelta(minutes=1)

    ended = store.end_link(
        link.link_id,
        ended_at=ended_at,
        end_reason="  user unlink  ",
        ended_by_principal_id=actor.principal_id,
    )

    assert ended.status == "ended"
    assert ended.ended_at == ended_at
    assert ended.end_reason == "user unlink"
    assert ended.ended_by_principal_id == (
        actor.principal_id
    )

    loaded = store.load_link(link.link_id)
    assert loaded == ended


def test_end_link_requires_existing_actor(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(link)

    with pytest.raises(
        PrincipalIdentityPrincipalNotFoundError,
    ):
        store.end_link(
            link.link_id,
            ended_at=NOW + timedelta(minutes=1),
            end_reason="administrative unlink",
            ended_by_principal_id=(
                create_principal_id()
            ),
        )

    assert store.load_link(link.link_id).status == (
        "active"
    )


def test_end_link_is_terminal(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(link)

    store.end_link(
        link.link_id,
        ended_at=NOW + timedelta(minutes=1),
        end_reason="user unlink",
    )

    with pytest.raises(
        PrincipalIdentityLinkTransitionError,
    ):
        store.end_link(
            link.link_id,
            ended_at=NOW + timedelta(minutes=2),
            end_reason="second unlink",
        )


def test_load_missing_link(
    database_path: Path,
):
    store = SQLitePrincipalIdentityStore(
        database_path
    )

    with pytest.raises(
        PrincipalIdentityLinkNotFoundError,
    ):
        store.load_link(
            create_principal_identity_link_id()
        )


def test_load_active_link_is_exact(
    database_path: Path,
):
    principal = _principal()
    provider = _provider(
        issuer="https://issuer.example",
    )

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
        subject="Subject-Exact",
    )
    store.create_link(link)

    with pytest.raises(
        PrincipalIdentityLinkNotFoundError,
    ):
        store.load_active_link(
            issuer="https://issuer.example",
            subject="subject-exact",
        )


def test_store_does_not_initialize_schema(
    tmp_path: Path,
):
    database_path = tmp_path / "uninitialized.db"
    store = SQLitePrincipalIdentityStore(
        database_path
    )

    with pytest.raises(Exception):
        store.create_provider(_provider())

    connection = sqlite3.connect(database_path)
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


def test_unknown_link_integrity_error_is_not_misclassified():
    error = sqlite3.IntegrityError(
        "CHECK constraint failed: unexpected_constraint"
    )

    with pytest.raises(
        PrincipalIdentityStoreError,
        match="Could not create principal identity link",
    ) as raised:
        SQLitePrincipalIdentityStore._raise_link_integrity_error(
            error,
            operation="create",
        )

    assert not isinstance(
        raised.value,
        PrincipalIdentityAlreadyLinkedError,
    )
    assert not isinstance(
        raised.value,
        PrincipalIdentityOwnershipConflictError,
    )
    assert raised.value.__cause__ is error


def test_identity_integrity_error_contract_matches_schema():
    ownership_message = (
        "External identity is historically "
        "owned by another principal"
    )
    active_unique_columns = (
        "issuer,\n"
        "    subject"
    )

    assert ownership_message in (
        CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL
    )
    assert (
        "idx_principal_identity_links_active"
        in CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL
    )
    assert active_unique_columns in (
        CREATE_PRINCIPAL_IDENTITY_FOUNDATION_SQL
    )


def test_end_link_allows_actorless_system_end(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    link = _link(
        provider=provider,
        principal=principal,
    )
    store.create_link(link)

    ended_at = NOW + timedelta(minutes=1)

    ended = store.end_link(
        link.link_id,
        ended_at=ended_at,
        end_reason="system unlink",
    )

    assert ended.status == "ended"
    assert ended.ended_at == ended_at
    assert ended.end_reason == "system unlink"
    assert ended.ended_by_principal_id is None

    assert store.load_link(link.link_id) == ended


def test_duplicate_link_constraint_path_maps_to_domain_error(
    database_path: Path,
):
    principal = _principal()
    provider = _provider()

    SQLitePrincipalStore(
        database_path
    ).create(principal)

    store = SQLitePrincipalIdentityStore(
        database_path
    )
    store.create_provider(provider)

    first = _link(
        provider=provider,
        principal=principal,
    )
    second = _link(
        provider=provider,
        principal=principal,
    )

    store.create_link(first)

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        with pytest.raises(
            sqlite3.IntegrityError,
        ) as captured:
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
                    second.link_id,
                    second.identity_provider_id,
                    second.issuer,
                    second.subject,
                    second.principal_id,
                    second.linked_at.isoformat(),
                ),
            )

        with pytest.raises(
            PrincipalIdentityAlreadyLinkedError,
        ):
            store._raise_link_integrity_error(
                captured.value,
                operation="create",
            )
    finally:
        connection.close()

