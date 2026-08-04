from __future__ import annotations

import pytest

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.oidc_token_verifier import (
    OIDCTokenInvalidError,
    OIDCTokenVerifierUnavailableError,
)
from execution_evidence.request_authenticator import (
    RequestAuthenticationFailedError,
    RequestAuthenticationRequiredError,
    RequestAuthenticationUnavailableError,
    RequestAuthenticator,
)
from execution_evidence.request_principal_resolver import (
    RequestPrincipalNotFoundError,
    RequestPrincipalResolutionStoreError,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


ISSUER = "https://issuer.example"
SUBJECT = "user-123"
TOKEN = "signed-token"


def _identity():
    return VerifiedOIDCIdentity(
        identity_provider_id="idp_123e4567-e89b-42d3-a456-426614174000",
        issuer=ISSUER,
        subject=SUBJECT,
    )


def _principal():
    return AuthenticatedRequestPrincipal(
        principal_id=(
            "prn_123e4567-e89b-42d3-a456-426614174000"
        ),
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-426614174001"
        ),
        identity_link_id=(
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
        issuer=ISSUER,
        subject=SUBJECT,
    )


class Verifier:
    def __init__(
        self,
        *,
        identity=None,
        error=None,
    ):
        self.identity = identity or _identity()
        self.error = error
        self.tokens = []

    def verify(self, token):
        self.tokens.append(token)

        if self.error is not None:
            raise self.error

        return self.identity


class Resolver:
    def __init__(
        self,
        *,
        principal=None,
        error=None,
    ):
        self.principal = principal or _principal()
        self.error = error
        self.identities = []

    def resolve(self, identity):
        self.identities.append(identity)

        if self.error is not None:
            raise self.error

        return self.principal


def test_authenticate_returns_durable_principal():
    verifier = Verifier()
    resolver = Resolver()

    result = RequestAuthenticator(
        token_verifier=verifier,
        principal_resolver=resolver,
    ).authenticate(
        f"Bearer {TOKEN}"
    )

    assert result == _principal()
    assert verifier.tokens == [TOKEN]
    assert resolver.identities == [_identity()]


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "Basic abc",
        "Bearer",
        "Bearer one two",
    ],
)
def test_authentication_requires_bearer_token(
    header,
):
    verifier = Verifier()
    resolver = Resolver()

    with pytest.raises(
        RequestAuthenticationRequiredError
    ):
        RequestAuthenticator(
            token_verifier=verifier,
            principal_resolver=resolver,
        ).authenticate(header)

    assert verifier.tokens == []
    assert resolver.identities == []


def test_bearer_scheme_is_case_insensitive():
    verifier = Verifier()

    RequestAuthenticator(
        token_verifier=verifier,
        principal_resolver=Resolver(),
    ).authenticate(
        f"bEaReR {TOKEN}"
    )

    assert verifier.tokens == [TOKEN]


def test_invalid_token_does_not_resolve_principal():
    resolver = Resolver()

    with pytest.raises(
        RequestAuthenticationFailedError,
        match="authentication failed",
    ):
        RequestAuthenticator(
            token_verifier=Verifier(
                error=OIDCTokenInvalidError(
                    "bad signature"
                )
            ),
            principal_resolver=resolver,
        ).authenticate(
            f"Bearer {TOKEN}"
        )

    assert resolver.identities == []


def test_unknown_identity_is_authentication_failure():
    with pytest.raises(
        RequestAuthenticationFailedError,
        match="authentication failed",
    ):
        RequestAuthenticator(
            token_verifier=Verifier(),
            principal_resolver=Resolver(
                error=RequestPrincipalNotFoundError(
                    "unknown"
                )
            ),
        ).authenticate(
            f"Bearer {TOKEN}"
        )


def test_verifier_outage_is_not_invalid_identity():
    with pytest.raises(
        RequestAuthenticationUnavailableError,
        match="temporarily unavailable",
    ):
        RequestAuthenticator(
            token_verifier=Verifier(
                error=OIDCTokenVerifierUnavailableError(
                    "jwks unavailable"
                )
            ),
            principal_resolver=Resolver(),
        ).authenticate(
            f"Bearer {TOKEN}"
        )


def test_identity_store_outage_is_not_auth_failure():
    with pytest.raises(
        RequestAuthenticationUnavailableError,
        match="temporarily unavailable",
    ):
        RequestAuthenticator(
            token_verifier=Verifier(),
            principal_resolver=Resolver(
                error=(
                    RequestPrincipalResolutionStoreError(
                        "database unavailable"
                    )
                )
            ),
        ).authenticate(
            f"Bearer {TOKEN}"
        )
