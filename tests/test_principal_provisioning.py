from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from threading import Barrier

import pytest

from execution_evidence.principal_provisioning import (
    ExistingPrincipal,
    PrincipalProvisioningAccessDenied,
    PrincipalProvisioningService,
    ProvisionedPrincipal,
    PrincipalProvisioningConfigurationError,
    PrincipalProvisioningUnavailableError,
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
    "idp_223e4567-e89b-42d3-a456-426614174111"
)
ISSUER = "https://accounts.google.com"
SUBJECT = "google-user-999"


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


def seed_provider(
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


def counts(
    path: Path,
) -> tuple[int, int]:
    connection = (
        connect_execution_evidence_database(
            path
        )
    )

    try:
        principals = connection.execute(
            """
            SELECT COUNT(*)
            FROM principals
            """
        ).fetchone()[0]

        links = connection.execute(
            """
            SELECT COUNT(*)
            FROM principal_identity_links
            """
        ).fetchone()[0]

        return int(principals), int(links)
    finally:
        connection.close()


def test_first_login_creates_one_principal_and_link(
    database_path: Path,
):
    seed_provider(database_path)

    result = PrincipalProvisioningService(
        database_path
    ).resolve_or_provision(
        identity(),
        now=NOW,
    )

    assert isinstance(
        result,
        ProvisionedPrincipal,
    )

    assert counts(database_path) == (1, 1)

    connection = (
        connect_execution_evidence_database(
            database_path
        )
    )

    try:
        row = connection.execute(
            """
            SELECT principal_kind, status
            FROM principals
            """
        ).fetchone()
    finally:
        connection.close()

    assert row["principal_kind"] == "human"
    assert row["status"] == "active"


def test_second_login_returns_existing(
    database_path: Path,
):
    seed_provider(database_path)

    service = PrincipalProvisioningService(
        database_path
    )

    first = service.resolve_or_provision(
        identity(),
        now=NOW,
    )

    second = service.resolve_or_provision(
        identity(),
        now=NOW + timedelta(seconds=1),
    )

    assert isinstance(
        first,
        ProvisionedPrincipal,
    )

    assert isinstance(
        second,
        ExistingPrincipal,
    )

    assert (
        first.principal.principal_id
        == second.principal.principal_id
    )

    assert counts(database_path) == (1, 1)


def test_disabled_provider_does_not_provision(
    database_path: Path,
):
    seed_provider(
        database_path,
        status="disabled",
    )

    result = PrincipalProvisioningService(
        database_path
    ).resolve_or_provision(
        identity(),
        now=NOW,
    )

    assert isinstance(
        result,
        PrincipalProvisioningAccessDenied,
    )
    assert (
        result.reason
        == "provider_disabled"
    )
    assert counts(database_path) == (0, 0)


def test_missing_provider_is_not_unknown_signup(
    database_path: Path,
):
    before = counts(database_path)

    with pytest.raises(
        PrincipalProvisioningConfigurationError,
        match="not registered",
    ):
        PrincipalProvisioningService(
            database_path
        ).resolve_or_provision(
            identity(),
            now=NOW,
        )

    # A missing operator-controlled provider is a deployment
    # configuration failure. It must never become an implicit
    # signup path or write durable identity state.
    assert counts(database_path) == before


def test_concurrent_first_login_converges(
    database_path: Path,
):
    seed_provider(database_path)

    workers = 8
    barrier = Barrier(workers)

    def login():
        service = PrincipalProvisioningService(
            database_path
        )

        barrier.wait()

        return service.resolve_or_provision(
            identity(),
            now=NOW,
        )

    with ThreadPoolExecutor(
        max_workers=workers,
    ) as executor:
        results = list(
            executor.map(
                lambda _: login(),
                range(workers),
            )
        )

    principal_ids = {
        result.principal.principal_id
        for result in results
        if isinstance(
            result,
            (
                ExistingPrincipal,
                ProvisionedPrincipal,
            ),
        )
    }

    assert len(principal_ids) == 1
    assert counts(database_path) == (1, 1)

    assert sum(
        isinstance(
            result,
            ProvisionedPrincipal,
        )
        for result in results
    ) == 1

    assert sum(
        isinstance(
            result,
            ExistingPrincipal,
        )
        for result in results
    ) == workers - 1


def test_timezone_is_required(
    database_path: Path,
):
    seed_provider(database_path)

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        PrincipalProvisioningService(
            database_path
        ).resolve_or_provision(
            identity(),
            now=datetime(
                2026,
                8,
                16,
                12,
                0,
            ),
        )


# === SOLVYN MILESTONE 1A HARDENING REGRESSIONS ===

import execution_evidence.principal_provisioning as provisioning_module

from execution_evidence.principal_provisioning import (
    PrincipalProvisioningConfigurationError,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


HARDENING_ISSUER = "https://accounts.google.com"


def _hardening_counts(database_path):
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        principal_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM principals
            """
        ).fetchone()[0]

        link_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM principal_identity_links
            """
        ).fetchone()[0]

        return principal_count, link_count
    finally:
        connection.close()


def _hardening_insert_provider(
    database_path,
    *,
    provider_id,
):
    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

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
                HARDENING_ISSUER,
                NOW.isoformat(),
                NOW.isoformat(),
            ),
        )

        connection.execute("COMMIT")
    finally:
        connection.close()


def _hardening_insert_identity_graph(
    database_path,
    *,
    provider_id,
    principal_id,
    link_id,
    subject,
    principal_status="active",
    ended=False,
):
    connection = connect_execution_evidence_database(
        database_path
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
            VALUES (
                ?,
                'human',
                ?,
                ?,
                ?
            )
            """,
            (
                principal_id,
                principal_status,
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
                ?, ?, ?, ?, ?,
                'active',
                ?,
                NULL, NULL, NULL,
                NULL, NULL, NULL
            )
            """,
            (
                link_id,
                provider_id,
                HARDENING_ISSUER,
                subject,
                principal_id,
                NOW.isoformat(),
            ),
        )

        if ended:
            connection.execute(
                """
                UPDATE principal_identity_links
                SET
                    status = 'ended',
                    ended_at = ?,
                    end_reason = 'security regression fixture'
                WHERE link_id = ?
                """,
                (
                    NOW.isoformat(),
                    link_id,
                ),
            )

        connection.execute("COMMIT")
    finally:
        connection.close()


def _hardening_identity(
    *,
    provider_id,
    subject,
):
    return VerifiedOIDCIdentity(
        identity_provider_id=provider_id,
        issuer=HARDENING_ISSUER,
        subject=subject,
    )


def test_provider_not_configured_is_configuration_failure(
    database_path,
):
    identity = VerifiedOIDCIdentity(
        identity_provider_id=(
            "idp_223e4567-e89b-42d3-a456-426614174000"
        ),
        issuer=HARDENING_ISSUER,
        subject="unconfigured-user",
    )

    before = _hardening_counts(database_path)

    with pytest.raises(
        PrincipalProvisioningConfigurationError,
        match="not registered",
    ):
        PrincipalProvisioningService(
            database_path
        ).resolve_or_provision(
            identity,
            now=NOW,
        )

    assert _hardening_counts(database_path) == before


@pytest.mark.parametrize(
    ("principal_status", "expected_reason"),
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
def test_inactive_principal_never_reprovisions(
    database_path,
    principal_status,
    expected_reason,
):
    provider_id = (
        "idp_323e4567-e89b-42d3-a456-426614174000"
    )
    principal_id = (
        "prn_323e4567-e89b-42d3-a456-426614174001"
    )
    link_id = (
        "pil_323e4567-e89b-42d3-a456-426614174002"
    )
    subject = (
        f"inactive-{principal_status}"
    )

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    _hardening_insert_identity_graph(
        database_path,
        provider_id=provider_id,
        principal_id=principal_id,
        link_id=link_id,
        subject=subject,
        principal_status=principal_status,
    )

    before = _hardening_counts(database_path)

    result = PrincipalProvisioningService(
        database_path
    ).resolve_or_provision(
        _hardening_identity(
            provider_id=provider_id,
            subject=subject,
        ),
        now=NOW,
    )

    assert isinstance(
        result,
        PrincipalProvisioningAccessDenied,
    )
    assert result.reason == expected_reason

    # Critical invariant:
    # login must not mint a replacement identity.
    assert _hardening_counts(database_path) == before


def test_ended_link_never_auto_relinks_or_reprovisions(
    database_path,
):
    provider_id = (
        "idp_423e4567-e89b-42d3-a456-426614174000"
    )
    principal_id = (
        "prn_423e4567-e89b-42d3-a456-426614174001"
    )
    link_id = (
        "pil_423e4567-e89b-42d3-a456-426614174002"
    )
    subject = "ended-user"

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    _hardening_insert_identity_graph(
        database_path,
        provider_id=provider_id,
        principal_id=principal_id,
        link_id=link_id,
        subject=subject,
        ended=True,
    )

    before = _hardening_counts(database_path)

    result = PrincipalProvisioningService(
        database_path
    ).resolve_or_provision(
        _hardening_identity(
            provider_id=provider_id,
            subject=subject,
        ),
        now=NOW,
    )

    assert isinstance(
        result,
        PrincipalProvisioningAccessDenied,
    )
    assert result.reason == "link_ended"

    assert _hardening_counts(database_path) == before


def test_link_insert_failure_rolls_back_new_principal(
    database_path,
    monkeypatch,
):
    """Prove principal + identity link are one transaction.

    We deliberately collide only on link_id.

    The candidate principal INSERT therefore succeeds first,
    then the identity-link INSERT fails. The transaction must
    roll the principal back as well.
    """

    provider_id = (
        "idp_523e4567-e89b-42d3-a456-426614174000"
    )

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    existing_principal_id = (
        "prn_523e4567-e89b-42d3-a456-426614174001"
    )
    duplicate_link_id = (
        "pil_523e4567-e89b-42d3-a456-426614174002"
    )

    # Existing identity uses a DIFFERENT subject, so the only
    # collision for the new login is the generated link_id.
    _hardening_insert_identity_graph(
        database_path,
        provider_id=provider_id,
        principal_id=existing_principal_id,
        link_id=duplicate_link_id,
        subject="already-existing-user",
    )

    before = _hardening_counts(database_path)

    monkeypatch.setattr(
        provisioning_module,
        "create_principal_identity_link_id",
        lambda: duplicate_link_id,
    )

    identity = _hardening_identity(
        provider_id=provider_id,
        subject="brand-new-user",
    )

    with pytest.raises(
        PrincipalProvisioningUnavailableError
    ):
        PrincipalProvisioningService(
            database_path
        ).resolve_or_provision(
            identity,
            now=NOW,
        )

    # This assertion proves the transaction guarantee rather
    # than merely inspecting the code.
    assert _hardening_counts(database_path) == before

    connection = connect_execution_evidence_database(
        database_path
    )

    try:
        leaked = connection.execute(
            """
            SELECT COUNT(*)
            FROM principals
            WHERE principal_id != ?
            """,
            (existing_principal_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert leaked == 0


# === SOLVYN MILESTONE 1A HARDENING PASS 2 ===


# === SOLVYN MILESTONE 1A HARDENING PASS 2 ===


class _DenyAllProvisioningPolicy(
    provisioning_module.PrincipalProvisioningPolicy
):
    def allows(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> bool:
        return False


def test_provisioning_policy_denial_writes_nothing(
    database_path,
):
    provider_id = (
        "idp_623e4567-e89b-42d3-a456-426614174000"
    )

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    before = _hardening_counts(database_path)

    result = PrincipalProvisioningService(
        database_path,
        policy=_DenyAllProvisioningPolicy(),
    ).resolve_or_provision(
        _hardening_identity(
            provider_id=provider_id,
            subject="policy-denied-user",
        ),
        now=NOW,
    )

    assert isinstance(
        result,
        PrincipalProvisioningAccessDenied,
    )
    assert result.reason == "policy_denied"
    assert _hardening_counts(database_path) == before


def test_stale_unknown_inspection_revalidates_inside_transaction(
    database_path,
    monkeypatch,
):
    """A stale UnknownIdentity result must not create a second user.

    The first inspection deliberately observes no identity link.
    Before provisioning begins, another actor commits the same
    external identity. The write transaction must re-read durable
    state and converge to that existing principal.
    """

    provider_id = (
        "idp_623e4567-e89b-42d3-a456-426614174001"
    )
    competing_principal_id = (
        "prn_623e4567-e89b-42d3-a456-426614174002"
    )
    competing_link_id = (
        "pil_623e4567-e89b-42d3-a456-426614174003"
    )
    subject = "stale-inspection-user"

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    service = PrincipalProvisioningService(
        database_path
    )

    original_inspect = service._resolver.inspect
    injected = {"done": False}

    def inspect_then_competitor(identity):
        inspection = original_inspect(identity)

        if (
            not injected["done"]
            and inspection.kind == "unknown_identity"
        ):
            _hardening_insert_identity_graph(
                database_path,
                provider_id=provider_id,
                principal_id=competing_principal_id,
                link_id=competing_link_id,
                subject=subject,
            )
            injected["done"] = True

        return inspection

    monkeypatch.setattr(
        service._resolver,
        "inspect",
        inspect_then_competitor,
    )

    result = service.resolve_or_provision(
        _hardening_identity(
            provider_id=provider_id,
            subject=subject,
        ),
        now=NOW,
    )

    assert injected["done"] is True
    assert isinstance(
        result,
        ExistingPrincipal,
    )
    assert (
        result.principal.principal_id
        == competing_principal_id
    )
    assert _hardening_counts(database_path) == (1, 1)


def test_generated_link_id_collision_is_not_misclassified_as_login_race(
    database_path,
    monkeypatch,
):
    """An unrelated UNIQUE failure must not invoke race reload."""

    provider_id = (
        "idp_623e4567-e89b-42d3-a456-426614174004"
    )
    existing_principal_id = (
        "prn_623e4567-e89b-42d3-a456-426614174005"
    )
    duplicate_link_id = (
        "pil_623e4567-e89b-42d3-a456-426614174006"
    )

    _hardening_insert_provider(
        database_path,
        provider_id=provider_id,
    )

    _hardening_insert_identity_graph(
        database_path,
        provider_id=provider_id,
        principal_id=existing_principal_id,
        link_id=duplicate_link_id,
        subject="unrelated-existing-user",
    )

    before = _hardening_counts(database_path)

    monkeypatch.setattr(
        provisioning_module,
        "create_principal_identity_link_id",
        lambda: duplicate_link_id,
    )

    service = PrincipalProvisioningService(
        database_path
    )

    def forbidden_reload(identity):
        raise AssertionError(
            "Generated link-ID collision must not be "
            "classified as a concurrent identity race."
        )

    monkeypatch.setattr(
        service,
        "_reload_after_race",
        forbidden_reload,
    )

    with pytest.raises(
        PrincipalProvisioningUnavailableError,
        match="unexpected durable constraint failure",
    ):
        service.resolve_or_provision(
            _hardening_identity(
                provider_id=provider_id,
                subject="brand-new-collision-user",
            ),
            now=NOW,
        )

    # The candidate principal insert happened before the
    # duplicate link-ID failure. Atomic rollback must still
    # leave the original graph as the only durable state.
    assert _hardening_counts(database_path) == before
