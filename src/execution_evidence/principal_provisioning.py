from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Union

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.principal import (
    create_principal_id,
)
from execution_evidence.principal_identity import (
    create_principal_identity_link_id,
)
from execution_evidence.principal_identity_inspection import (
    PrincipalIdentityInspection,
)
from execution_evidence.request_principal_resolver import (
    RequestPrincipalResolutionStoreError,
)
from execution_evidence.sqlite_request_principal_resolver import (
    SQLiteRequestPrincipalResolver,
)
from execution_evidence.sqlite_schema import (
    connect_execution_evidence_database,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


PrincipalProvisioningDeniedReason = Literal[
    "link_ended",
    "principal_suspended",
    "principal_deactivated",
    "provider_disabled",
    "policy_denied",
]


class PrincipalProvisioningError(
    RuntimeError
):
    pass


class PrincipalProvisioningUnavailableError(
    PrincipalProvisioningError
):
    pass


class PrincipalProvisioningConfigurationError(
    PrincipalProvisioningError
):
    """Interactive identity provisioning is misconfigured.

    This is deliberately distinct from AccessDenied.

    A verified external identity reaching a provider that has
    not been operator-registered is a deployment/configuration
    failure, not a statement about the user's authorization.
    """
    pass


@dataclass(frozen=True)
class ExistingPrincipal:
    principal: AuthenticatedRequestPrincipal

    status: Literal["existing"] = "existing"


@dataclass(frozen=True)
class ProvisionedPrincipal:
    principal: AuthenticatedRequestPrincipal

    status: Literal["provisioned"] = (
        "provisioned"
    )


@dataclass(frozen=True)
class PrincipalProvisioningAccessDenied:
    reason: PrincipalProvisioningDeniedReason

    status: Literal["access_denied"] = (
        "access_denied"
    )


PrincipalProvisioningResult = Union[
    ExistingPrincipal,
    ProvisionedPrincipal,
    PrincipalProvisioningAccessDenied,
]


class PrincipalProvisioningPolicy:
    """Policy seam for future signup restrictions."""

    def allows(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> bool:
        return True


class PrincipalProvisioningService:
    """Resolve or provision one Solvyn human principal.

    This service belongs to the LOGIN CALLBACK path.

    It must never be called by RequestAuthenticator,
    because ordinary bearer-authenticated API requests
    are intentionally read-only with respect to durable
    principal identity state.
    """

    def __init__(
        self,
        database_path: Path | str,
        *,
        policy: (
            PrincipalProvisioningPolicy
            | None
        ) = None,
    ) -> None:
        self._path = Path(database_path)
        self._resolver = (
            SQLiteRequestPrincipalResolver(
                self._path
            )
        )
        self._policy = (
            policy
            or PrincipalProvisioningPolicy()
        )

    def resolve_or_provision(
        self,
        identity: VerifiedOIDCIdentity,
        *,
        now: datetime,
    ) -> PrincipalProvisioningResult:
        if not isinstance(
            identity,
            VerifiedOIDCIdentity,
        ):
            raise TypeError(
                "Principal provisioning requires a "
                "verified OIDC identity."
            )

        if (
            now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise ValueError(
                "Principal provisioning timestamp "
                "must be timezone-aware."
            )

        inspection = self._resolver.inspect(
            identity
        )

        existing = self._result_from_inspection(
            inspection
        )

        if existing is not None:
            return existing

        if not self._policy.allows(identity):
            return (
                PrincipalProvisioningAccessDenied(
                    reason="policy_denied"
                )
            )

        return self._provision(
            identity,
            now=now,
        )

    def _result_from_inspection(
        self,
        inspection: PrincipalIdentityInspection,
    ) -> PrincipalProvisioningResult | None:
        if inspection.kind == "active":
            return ExistingPrincipal(
                principal=(
                    inspection.require_active()
                )
            )

        if inspection.kind == "unknown_identity":
            return None

        if inspection.kind == "link_ended":
            return (
                PrincipalProvisioningAccessDenied(
                    reason="link_ended"
                )
            )

        if (
            inspection.kind
            == "principal_suspended"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason=(
                        "principal_suspended"
                    )
                )
            )

        if (
            inspection.kind
            == "principal_deactivated"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason=(
                        "principal_deactivated"
                    )
                )
            )

        if (
            inspection.kind
            == "provider_disabled"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason="provider_disabled"
                )
            )

        if (
            inspection.kind
            == "provider_not_configured"
        ):
            raise PrincipalProvisioningConfigurationError(
                "Verified OIDC provider is not registered "
                "in durable identity-provider storage."
            )

        raise PrincipalProvisioningError(
            "Unsupported identity inspection "
            f"outcome: {inspection.kind!r}."
        )

    def _provision(
        self,
        identity: VerifiedOIDCIdentity,
        *,
        now: datetime,
    ) -> PrincipalProvisioningResult:
        connection = (
            connect_execution_evidence_database(
                self._path
            )
        )

        principal_id = create_principal_id()
        link_id = (
            create_principal_identity_link_id()
        )

        try:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            # -----------------------------------------
            # Provider is operator-controlled.
            # Revalidate it INSIDE the write txn.
            # -----------------------------------------
            provider = connection.execute(
                """
                SELECT
                    identity_provider_id,
                    issuer,
                    status
                FROM identity_providers
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                """,
                (
                    identity.identity_provider_id,
                    identity.issuer,
                ),
            ).fetchone()

            if provider is None:
                connection.execute("ROLLBACK")
                raise (
                    PrincipalProvisioningConfigurationError(
                        "Verified OIDC provider is not "
                        "registered in durable "
                        "identity-provider storage."
                    )
                )

            if provider["status"] != "active":
                connection.execute("ROLLBACK")
                return (
                    PrincipalProvisioningAccessDenied(
                        reason="provider_disabled"
                    )
                )

            # -----------------------------------------
            # Revalidate complete link history.
            #
            # Active:
            #   concurrent winner already provisioned.
            #
            # Ended:
            #   deliberately blocked from automatic
            #   relinking.
            #
            # Reserved severed_* columns are not an
            # authentication release path in the current
            # trusted schema.
            # -----------------------------------------
            existing_link = connection.execute(
                """
                SELECT
                    link_id,
                    principal_id,
                    status,
                    severed_at
                FROM principal_identity_links
                WHERE
                    identity_provider_id = ?
                    AND issuer = ?
                    AND subject = ?
                ORDER BY
                    identity_link_row_id DESC
                LIMIT 1
                """,
                (
                    identity.identity_provider_id,
                    identity.issuer,
                    identity.subject,
                ),
            ).fetchone()

            if existing_link is not None:
                if (
                    existing_link["status"]
                    == "active"
                ):
                    connection.execute(
                        "ROLLBACK"
                    )

                    return (
                        self._reload_after_race(
                            identity
                        )
                    )

                # Any remaining historical link is an
                # ended identity relationship. Current trusted
                # schema deliberately makes ended links terminal;
                # first-login provisioning must never reinterpret
                # reserved severed_* metadata as an automatic
                # identity-release path.
                connection.execute(
                    "ROLLBACK"
                )

                return (
                    PrincipalProvisioningAccessDenied(
                        reason="link_ended"
                    )
                )

            created_at = now.isoformat()

            # -----------------------------------------
            # Both inserts share THIS connection and
            # THIS transaction.
            #
            # No workspace is created here.
            # -----------------------------------------
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
                    'active',
                    ?,
                    ?
                )
                """,
                (
                    principal_id,
                    created_at,
                    created_at,
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
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'active',
                    ?,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL,
                    NULL
                )
                """,
                (
                    link_id,
                    identity.identity_provider_id,
                    identity.issuer,
                    identity.subject,
                    principal_id,
                    created_at,
                ),
            )

            connection.execute("COMMIT")

        except sqlite3.IntegrityError as error:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass

            # Only identity-ownership/active-link conflicts
            # are eligible for the one-time convergence
            # reload below.
            #
            # An unrelated integrity failure must remain an
            # infrastructure/storage failure. Treating every
            # constraint failure as a login race would hide
            # real database defects behind normal auth flow.
            if not self._is_identity_race_integrity_error(
                error
            ):
                raise (
                    PrincipalProvisioningUnavailableError(
                        "Principal provisioning encountered "
                        "an unexpected durable constraint "
                        "failure."
                    )
                ) from error

            # A concurrent login may have won after
            # our initial inspection.
            #
            # Reload ONCE. Never retry provisioning
            # in a loop.
            try:
                return self._reload_after_race(
                    identity
                )
            except Exception:
                raise (
                    PrincipalProvisioningUnavailableError(
                        "Principal provisioning "
                        "encountered a durable identity "
                        "conflict."
                    )
                ) from error

        except sqlite3.Error as error:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass

            raise (
                PrincipalProvisioningUnavailableError(
                    "Principal provisioning storage "
                    "is temporarily unavailable."
                )
            ) from error

        finally:
            connection.close()

        try:
            resolved = self._resolver.resolve(
                identity
            )
        except Exception as error:
            raise (
                PrincipalProvisioningUnavailableError(
                    "Provisioned principal could not "
                    "be resolved after commit."
                )
            ) from error

        return ProvisionedPrincipal(
            principal=resolved
        )

    @staticmethod
    def _is_identity_race_integrity_error(
        error: sqlite3.IntegrityError,
    ) -> bool:
        """Return whether this can be a concurrent-login race.

        Only durable external-identity ownership conflicts are
        eligible for the one-time convergence reload.

        Generated identifier collisions and unrelated database
        integrity failures are infrastructure failures, not
        authentication races.
        """

        message = str(error)

        active_identity_unique = (
            "UNIQUE constraint failed: "
            "principal_identity_links.issuer, "
            "principal_identity_links.subject"
        )

        historical_ownership = (
            "External identity is historically "
            "owned by another principal"
        )

        return (
            active_identity_unique in message
            or historical_ownership in message
        )


    def _reload_after_race(
        self,
        identity: VerifiedOIDCIdentity,
    ) -> PrincipalProvisioningResult:
        inspection = self._resolver.inspect(
            identity
        )

        if inspection.kind == "active":
            return ExistingPrincipal(
                principal=(
                    inspection.require_active()
                )
            )

        if inspection.kind == "link_ended":
            return (
                PrincipalProvisioningAccessDenied(
                    reason="link_ended"
                )
            )

        if (
            inspection.kind
            == "principal_suspended"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason=(
                        "principal_suspended"
                    )
                )
            )

        if (
            inspection.kind
            == "principal_deactivated"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason=(
                        "principal_deactivated"
                    )
                )
            )

        if (
            inspection.kind
            == "provider_disabled"
        ):
            return (
                PrincipalProvisioningAccessDenied(
                    reason="provider_disabled"
                )
            )

        if (
            inspection.kind
            == "provider_not_configured"
        ):
            raise PrincipalProvisioningConfigurationError(
                "Verified OIDC provider is not registered "
                "in durable identity-provider storage."
            )

        raise (
            PrincipalProvisioningUnavailableError(
                "Concurrent principal provisioning "
                "did not converge to an active "
                "durable principal."
            )
        )
