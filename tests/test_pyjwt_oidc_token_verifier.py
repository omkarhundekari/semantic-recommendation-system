from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from execution_evidence.oidc_jwks import (
    CachedOIDCJWKSProvider,
    OIDCJWKSFetcher,
    OIDCJWKSUnavailableError,
)
from execution_evidence.oidc_provider_config import (
    OIDCProviderConfig,
    OIDCProviderConfigRegistry,
)
from execution_evidence.oidc_token_verifier import (
    OIDCTokenInvalidError,
    OIDCTokenVerifierUnavailableError,
)
from execution_evidence.pyjwt_oidc_token_verifier import (
    MAX_OIDC_BEARER_TOKEN_BYTES,
    PyJWTOIDCTokenVerifier,
)


ISSUER = "https://issuer.example"
AUDIENCE = "solvyn-api"
PROVIDER_ID = (
    "idp_123e4567-e89b-42d3-a456-426614174000"
)
KID = "key-1"
NOW = datetime.now(timezone.utc)


class Fetcher(OIDCJWKSFetcher):
    def __init__(
        self,
        keys,
        *,
        error=None,
    ):
        self.keys = tuple(keys)
        self.error = error
        self.calls = 0

    def fetch(self, config):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return self.keys


def _config(**changes):
    values = {
        "identity_provider_id": PROVIDER_ID,
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_uri": (
            "https://issuer.example/.well-known/jwks.json"
        ),
    }
    values.update(changes)
    return OIDCProviderConfig(**values)


def _private_key(bits=2048):
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
    )


def _jwk(
    private_key,
    *,
    kid=KID,
    **changes,
):
    value = json.loads(
        RSAAlgorithm.to_jwk(
            private_key.public_key()
        )
    )
    value["kid"] = kid
    value["alg"] = "RS256"
    value["use"] = "sig"
    value.update(changes)
    return value


def _token(
    private_key,
    *,
    issuer=ISSUER,
    audience=AUDIENCE,
    subject="subject-123",
    kid=KID,
    algorithm="RS256",
    exp=None,
    nbf=None,
    extra_claims=None,
):
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": subject,
        "exp": (
            exp
            or NOW + timedelta(minutes=10)
        ),
    }

    if nbf is not None:
        claims["nbf"] = nbf

    if extra_claims:
        claims.update(extra_claims)

    return jwt.encode(
        claims,
        private_key,
        algorithm=algorithm,
        headers={"kid": kid},
    )


def _verifier(
    *,
    keys,
    config=None,
    fetch_error=None,
):
    fetcher = Fetcher(
        keys,
        error=fetch_error,
    )

    verifier = PyJWTOIDCTokenVerifier(
        provider_registry=(
            OIDCProviderConfigRegistry(
                (config or _config(),)
            )
        ),
        jwks_provider=CachedOIDCJWKSProvider(
            fetcher=fetcher
        ),
    )

    return verifier, fetcher


def test_verifies_rs256_token_and_binds_provider():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    identity = verifier.verify(
        _token(private_key)
    )

    assert (
        identity.identity_provider_id
        == PROVIDER_ID
    )
    assert identity.issuer == ISSUER
    assert identity.subject == "subject-123"


def test_unknown_issuer_is_invalid():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            _token(
                private_key,
                issuer="https://other.example",
            )
        )


@pytest.mark.parametrize(
    "audience",
    [
        "other-api",
        "",
        [],
    ],
)
def test_wrong_or_empty_audience_is_invalid(
    audience,
):
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            _token(
                private_key,
                audience=audience,
            )
        )


def test_audience_array_accepts_configured_value():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    identity = verifier.verify(
        _token(
            private_key,
            audience=[
                "other-api",
                AUDIENCE,
            ],
        )
    )

    assert identity.subject == "subject-123"


def test_expired_token_is_invalid():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            _token(
                private_key,
                exp=NOW - timedelta(minutes=5),
            )
        )


def test_future_nbf_is_invalid():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            _token(
                private_key,
                nbf=NOW + timedelta(minutes=5),
            )
        )


def test_blank_subject_is_invalid():
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            _token(
                private_key,
                subject="",
            )
        )


def test_missing_kid_is_invalid():
    private_key = _private_key()
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "subject-123",
        "exp": NOW + timedelta(minutes=5),
    }

    token = jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
    )

    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(token)


def test_unknown_kid_during_refresh_throttle_is_unavailable():
    private_key = _private_key()
    verifier, fetcher = _verifier(
        keys=[
            _jwk(
                private_key,
                kid="other-key",
            )
        ]
    )

    with pytest.raises(
        OIDCTokenVerifierUnavailableError,
        match="temporarily unavailable",
    ):
        verifier.verify(
            _token(private_key)
        )

    assert fetcher.calls == 1


def test_unknown_kid_after_allowed_refresh_is_invalid():
    private_key = _private_key()

    class Clock:
        def __init__(self):
            self.value = 1000.0

        def __call__(self):
            return self.value

    clock = Clock()

    class SequentialFetcher(OIDCJWKSFetcher):
        def __init__(self):
            self.calls = 0

        def fetch(self, config):
            self.calls += 1

            return (
                _jwk(
                    private_key,
                    kid="other-key",
                ),
            )

    fetcher = SequentialFetcher()

    verifier = PyJWTOIDCTokenVerifier(
        provider_registry=(
            OIDCProviderConfigRegistry(
                (_config(),)
            )
        ),
        jwks_provider=CachedOIDCJWKSProvider(
            fetcher=fetcher,
            monotonic=clock,
        ),
    )

    token = _token(private_key)

    with pytest.raises(
        OIDCTokenVerifierUnavailableError
    ):
        verifier.verify(token)

    assert fetcher.calls == 1

    clock.value += 61

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(token)

    assert fetcher.calls == 2


def test_jwks_outage_is_unavailable():
    private_key = _private_key()

    verifier, _ = _verifier(
        keys=[],
        fetch_error=OIDCJWKSUnavailableError(
            "network unavailable"
        ),
    )

    with pytest.raises(
        OIDCTokenVerifierUnavailableError
    ):
        verifier.verify(
            _token(private_key)
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"kty": "EC"},
        {"use": "enc"},
        {"key_ops": ["sign"]},
        {"alg": "RS512"},
    ],
)
def test_incompatible_jwk_is_unavailable(
    changes,
):
    private_key = _private_key()
    verifier, _ = _verifier(
        keys=[
            _jwk(
                private_key,
                **changes,
            )
        ]
    )

    with pytest.raises(
        OIDCTokenVerifierUnavailableError
    ):
        verifier.verify(
            _token(private_key)
        )


def test_jwk_alg_may_be_absent():
    private_key = _private_key()
    jwk = _jwk(private_key)
    jwk.pop("alg")

    verifier, _ = _verifier(
        keys=[jwk]
    )

    assert (
        verifier.verify(
            _token(private_key)
        ).subject
        == "subject-123"
    )


def test_weak_rsa_key_is_unavailable():
    private_key = _private_key(bits=1024)
    verifier, _ = _verifier(
        keys=[_jwk(private_key)]
    )

    with pytest.raises(
        OIDCTokenVerifierUnavailableError,
        match="too weak",
    ):
        verifier.verify(
            _token(private_key)
        )


def test_oversized_bearer_token_is_invalid():
    verifier, _ = _verifier(keys=[])

    with pytest.raises(
        OIDCTokenInvalidError
    ):
        verifier.verify(
            "x" * (
                MAX_OIDC_BEARER_TOKEN_BYTES
                + 1
            )
        )


def test_provider_selected_from_unverified_issuer_is_bound():
    first_key = _private_key()
    second_key = _private_key()

    first = _config()

    second = OIDCProviderConfig(
        identity_provider_id=(
            "idp_223e4567-e89b-42d3-a456-426614174000"
        ),
        issuer="https://second.example",
        audience="second-api",
        jwks_uri=(
            "https://second.example/.well-known/jwks.json"
        ),
    )

    class MultiFetcher(OIDCJWKSFetcher):
        def fetch(self, config):
            if (
                config.identity_provider_id
                == first.identity_provider_id
            ):
                return (_jwk(first_key),)

            return (
                _jwk(
                    second_key,
                    kid="second-key",
                ),
            )

    verifier = PyJWTOIDCTokenVerifier(
        provider_registry=(
            OIDCProviderConfigRegistry(
                (first, second)
            )
        ),
        jwks_provider=CachedOIDCJWKSProvider(
            fetcher=MultiFetcher()
        ),
    )

    identity = verifier.verify(
        _token(first_key)
    )

    assert (
        identity.identity_provider_id
        == first.identity_provider_id
    )
