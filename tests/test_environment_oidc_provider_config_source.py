from __future__ import annotations

import json

import pytest

from execution_evidence.environment_oidc_provider_config_source import (
    MAX_OIDC_PROVIDER_CONFIG_BYTES,
    OIDC_PROVIDERS_JSON_ENV,
    EnvironmentOIDCProviderConfigSource,
)
from execution_evidence.oidc_provider_config_source import (
    OIDCProviderConfigSourceError,
)


PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)


def _payload():
    return [
        {
            "identity_provider_id": PROVIDER_ID,
            "issuer": "https://issuer.example",
            "audience": "solvyn-api",
            "jwks_uri": (
                "https://issuer.example/.well-known/jwks.json"
            ),
            "allowed_algorithms": ["RS256"],
        }
    ]


def _source(value):
    return EnvironmentOIDCProviderConfigSource(
        environ={
            OIDC_PROVIDERS_JSON_ENV: value
        }
    )


def test_loads_provider_configuration_atomically():
    configs = _source(
        json.dumps(_payload())
    ).load()

    assert len(configs) == 1
    assert configs[0].identity_provider_id == (
        PROVIDER_ID
    )
    assert configs[0].issuer == (
        "https://issuer.example"
    )
    assert configs[0].allowed_algorithms == (
        "RS256",
    )


def test_missing_configuration_is_rejected():
    source = EnvironmentOIDCProviderConfigSource(
        environ={}
    )

    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="not configured",
    ):
        source.load()


def test_invalid_json_is_rejected():
    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="valid JSON",
    ):
        _source("{bad-json").load()


@pytest.mark.parametrize(
    "value",
    [
        json.dumps({}),
        json.dumps("provider"),
        json.dumps(123),
    ],
)
def test_configuration_must_be_array(
    value,
):
    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="JSON array",
    ):
        _source(value).load()


def test_empty_provider_array_is_rejected():
    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="provider count",
    ):
        _source("[]").load()


def test_duplicate_provider_id_is_rejected():
    payload = _payload()
    duplicate = dict(payload[0])
    duplicate["issuer"] = (
        "https://issuer-two.example"
    )
    duplicate["jwks_uri"] = (
        "https://issuer-two.example/jwks"
    )
    payload.append(duplicate)

    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="provider IDs must be unique",
    ):
        _source(json.dumps(payload)).load()


def test_duplicate_issuer_is_rejected():
    payload = _payload()
    duplicate = dict(payload[0])
    duplicate["identity_provider_id"] = (
        "idp_223e4567-e89b-42d3-a456-426614174000"
    )
    payload.append(duplicate)

    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="issuers must be unique",
    ):
        _source(json.dumps(payload)).load()


def test_oversized_configuration_is_rejected():
    oversized = (
        "x"
        * (MAX_OIDC_PROVIDER_CONFIG_BYTES + 1)
    )

    with pytest.raises(
        OIDCProviderConfigSourceError,
        match="maximum allowed size",
    ):
        _source(oversized).load()
