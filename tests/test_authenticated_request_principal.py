from __future__ import annotations

import pytest
from pydantic import ValidationError

from execution_evidence.authenticated_request_principal import (
    AuthenticatedRequestPrincipal,
)
from execution_evidence.verified_oidc_identity import (
    VerifiedOIDCIdentity,
)


def _principal(**changes):
    values = {
        "principal_id": (
            "prn_123e4567-e89b-42d3-a456-426614174000"
        ),
        "identity_provider_id": (
            "idp_123e4567-e89b-42d3-a456-426614174001"
        ),
        "identity_link_id": (
            "pil_123e4567-e89b-42d3-a456-426614174002"
        ),
        "issuer": "https://issuer.example",
        "subject": "subject-123",
    }
    values.update(changes)
    return AuthenticatedRequestPrincipal(**values)


def test_authenticated_principal_is_immutable():
    principal = _principal()

    with pytest.raises(ValidationError):
        principal.subject = "other"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("principal_id", "prn_bad"),
        ("identity_provider_id", "idp_bad"),
        ("identity_link_id", "pil_bad"),
        ("issuer", " https://issuer.example "),
        ("subject", " subject "),
    ],
)
def test_authenticated_principal_rejects_noncanonical_identity(
    field,
    value,
):
    with pytest.raises(ValidationError):
        _principal(**{field: value})


def test_verified_oidc_identity_preserves_exact_values():
    identity = VerifiedOIDCIdentity(
        identity_provider_id=(
            "idp_123e4567-e89b-42d3-a456-426614174000"
        ),
        issuer="https://issuer.example/path",
        subject="CaseSensitiveSubject",
    )

    assert (
        identity.issuer
        == "https://issuer.example/path"
    )
    assert identity.subject == "CaseSensitiveSubject"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "identity_provider_id",
            " idp_123e4567-e89b-42d3-a456-426614174000 ",
        ),
        (
            "identity_provider_id",
            "provider_123e4567-e89b-42d3-a456-426614174000",
        ),
        ("issuer", " https://issuer.example "),
        ("subject", " subject "),
        ("issuer", ""),
        ("subject", ""),
    ],
)
def test_verified_oidc_identity_rejects_noncanonical_values(
    field,
    value,
):
    values = {
        "identity_provider_id": (
            "idp_123e4567-e89b-42d3-a456-426614174000"
        ),
        "issuer": "https://issuer.example",
        "subject": "subject",
    }
    values[field] = value

    with pytest.raises(ValidationError):
        VerifiedOIDCIdentity(**values)
