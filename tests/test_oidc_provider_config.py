from __future__ import annotations

import pytest
from pydantic import ValidationError

from execution_evidence.oidc_provider_config import (
    OIDCProviderConfigurationNotFoundError,
    OIDCProviderConfig,
    OIDCProviderConfigRegistry,
)


PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)


def _config(**changes):
    values = {
        "identity_provider_id": PROVIDER_ID,
        "issuer": "https://issuer.example",
        "audience": "solvyn-api",
        "jwks_uri": "https://issuer.example/jwks",
    }
    values.update(changes)
    return OIDCProviderConfig(**values)


def test_registry_resolves_exact_issuer():
    config = _config()

    registry = OIDCProviderConfigRegistry(
        (config,)
    )

    assert (
        registry.load_by_issuer(
            config.issuer
        )
        == config
    )


def test_registry_does_not_normalize_issuer():
    registry = OIDCProviderConfigRegistry(
        (_config(),)
    )

    with pytest.raises(
        OIDCProviderConfigurationNotFoundError
    ):
        registry.load_by_issuer(
            "https://ISSUER.example"
        )


@pytest.mark.parametrize(
    "jwks_uri",
    [
        "http://issuer.example/jwks",
        "https://user:pass@issuer.example/jwks",
        "https://issuer.example/jwks#fragment",
        "not-a-url",
    ],
)
def test_jwks_uri_must_be_safe_https_configuration(
    jwks_uri,
):
    with pytest.raises(ValidationError):
        _config(jwks_uri=jwks_uri)


def test_rs256_is_the_only_supported_algorithm():
    with pytest.raises(
        ValidationError
    ):
        _config(
            allowed_algorithms=("RS256", "HS256")
        )


def test_duplicate_issuer_configuration_is_rejected():
    with pytest.raises(
        ValueError,
        match="issuer must be unique",
    ):
        OIDCProviderConfigRegistry(
            (
                _config(),
                _config(
                    identity_provider_id=(
                        "idp_223e4567-e89b-42d3-a456-426614174000"
                    )
                ),
            )
        )
