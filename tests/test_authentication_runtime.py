from __future__ import annotations

import json
from pathlib import Path

from execution_evidence.authentication_runtime import (
    build_authentication_runtime,
)
from execution_evidence.environment_oidc_provider_config_source import (
    OIDC_PROVIDERS_JSON_ENV,
    EnvironmentOIDCProviderConfigSource,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)


PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)


def _source():
    return EnvironmentOIDCProviderConfigSource(
        environ={
            OIDC_PROVIDERS_JSON_ENV: json.dumps(
                [
                    {
                        "identity_provider_id": (
                            PROVIDER_ID
                        ),
                        "issuer": (
                            "https://issuer.example"
                        ),
                        "audience": "solvyn-api",
                        "jwks_uri": (
                            "https://issuer.example/jwks"
                        ),
                    }
                ]
            )
        }
    )


def test_ready_runtime_builds_shared_authenticator(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at="2026-08-04T12:00:00+00:00",
    )

    trusted_service = TrustedSQLiteStorageService(
        database_path
    )

    runtime = build_authentication_runtime(
        config_source=_source(),
        trusted_sqlite_service=trusted_service,
    )

    assert runtime.status == "ready"
    assert runtime.ready is True
    assert runtime.authenticator is not None
    assert runtime.configured_provider_ids == (
        PROVIDER_ID,
    )
    assert runtime.errors == ()

    verifier = (
        runtime.authenticator._token_verifier
    )

    assert verifier._jwks_provider is not None


def test_missing_config_fails_closed_without_crashing():
    runtime = build_authentication_runtime(
        config_source=(
            EnvironmentOIDCProviderConfigSource(
                environ={}
            )
        ),
        trusted_sqlite_service=None,
    )

    assert runtime.status == "misconfigured"
    assert runtime.ready is False
    assert runtime.authenticator is None
    assert runtime.configured_provider_ids == ()
    assert runtime.errors


def test_storage_unavailability_is_distinct_from_config_error():
    runtime = build_authentication_runtime(
        config_source=_source(),
        trusted_sqlite_service=None,
    )

    assert runtime.status == (
        "unavailable_storage"
    )
    assert runtime.ready is False
    assert runtime.authenticator is None
    assert runtime.configured_provider_ids == (
        PROVIDER_ID,
    )
    assert runtime.errors == (
        "Durable principal resolution storage "
        "is unavailable.",
    )
