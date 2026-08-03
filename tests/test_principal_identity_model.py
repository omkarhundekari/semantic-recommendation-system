from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest
from pydantic import ValidationError

from execution_evidence.principal import (
    create_principal_id,
)
from execution_evidence.principal_identity import (
    IdentityProvider,
    PrincipalIdentityLink,
    create_identity_provider_id,
    create_principal_identity_link_id,
)


NOW = datetime(
    2026,
    8,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)


def _provider(**overrides):
    values = {
        "identity_provider_id": (
            create_identity_provider_id()
        ),
        "provider_kind": "google",
        "issuer": "https://accounts.google.com",
        "status": "active",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return IdentityProvider(**values)


def _link(**overrides):
    values = {
        "link_id": (
            create_principal_identity_link_id()
        ),
        "identity_provider_id": (
            create_identity_provider_id()
        ),
        "issuer": "https://accounts.google.com",
        "subject": "external-subject-123",
        "principal_id": create_principal_id(),
        "status": "active",
        "linked_at": NOW,
    }
    values.update(overrides)
    return PrincipalIdentityLink(**values)


def test_identity_provider_is_immutable():
    provider = _provider()

    with pytest.raises(
        ValidationError,
        match="frozen",
    ):
        provider.status = "disabled"


def test_identity_provider_rejects_noncanonical_id():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _provider(
            identity_provider_id=(
                "idp_00000000-0000-0000-0000-"
                "000000000000"
            )
        )


def test_identity_provider_preserves_exact_issuer():
    issuer = "https://issuer.example/"

    provider = _provider(issuer=issuer)

    assert provider.issuer == issuer


def test_identity_provider_rejects_issuer_whitespace():
    with pytest.raises(
        ValidationError,
        match="surrounding whitespace",
    ):
        _provider(
            issuer=" https://issuer.example"
        )


def test_identity_provider_requires_timezone():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _provider(
            created_at=NOW.replace(tzinfo=None)
        )


def test_identity_provider_timestamps_are_monotonic():
    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _provider(
            updated_at=NOW - timedelta(seconds=1)
        )


def test_active_identity_link_is_valid():
    link = _link()

    assert link.status == "active"
    assert link.ended_at is None
    assert link.end_reason is None
    assert link.ended_by_principal_id is None


def test_identity_link_is_immutable():
    link = _link()

    with pytest.raises(
        ValidationError,
        match="frozen",
    ):
        link.status = "ended"


def test_identity_link_rejects_noncanonical_id():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _link(
            link_id=(
                "pil_00000000-0000-0000-0000-"
                "000000000000"
            )
        )


def test_identity_link_rejects_provider_id_shape():
    with pytest.raises(
        ValidationError,
        match="start with 'idp_'",
    ):
        _link(identity_provider_id="provider")


def test_identity_link_preserves_exact_subject():
    link = _link(subject="CaseSensitiveSubject")

    assert link.subject == "CaseSensitiveSubject"


def test_identity_link_rejects_identity_whitespace():
    with pytest.raises(
        ValidationError,
        match="surrounding whitespace",
    ):
        _link(subject=" subject ")


def test_identity_link_rejects_malformed_principal_id():
    with pytest.raises(
        ValidationError,
        match="start with 'prn_'",
    ):
        _link(principal_id="principal")


def test_identity_link_rejects_malformed_ending_principal_id():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _link(
            status="ended",
            ended_at=NOW + timedelta(minutes=1),
            end_reason="administrative unlink",
            ended_by_principal_id=(
                "prn_00000000-0000-0000-0000-"
                "000000000000"
            ),
        )


def test_active_link_rejects_termination_metadata():
    with pytest.raises(
        ValidationError,
        match="termination metadata",
    ):
        _link(
            ended_at=NOW + timedelta(minutes=1),
            end_reason="user unlink",
        )


def test_ended_link_requires_ended_at():
    with pytest.raises(
        ValidationError,
        match="require ended_at",
    ):
        _link(
            status="ended",
            end_reason="user unlink",
        )


def test_ended_link_requires_reason():
    with pytest.raises(
        ValidationError,
        match="require an end reason",
    ):
        _link(
            status="ended",
            ended_at=NOW + timedelta(minutes=1),
        )


def test_end_reason_is_normalized():
    link = _link(
        status="ended",
        ended_at=NOW + timedelta(minutes=1),
        end_reason="  user unlink  ",
    )

    assert link.end_reason == "user unlink"


def test_blank_end_reason_is_rejected_for_ended_link():
    with pytest.raises(
        ValidationError,
        match="require an end reason",
    ):
        _link(
            status="ended",
            ended_at=NOW + timedelta(minutes=1),
            end_reason="   ",
        )


def test_ended_at_cannot_precede_linked_at():
    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _link(
            status="ended",
            ended_at=NOW - timedelta(seconds=1),
            end_reason="user unlink",
        )


def test_link_timestamps_require_timezone():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _link(
            linked_at=NOW.replace(tzinfo=None)
        )


def test_generated_identity_ids_are_distinct():
    provider_ids = {
        create_identity_provider_id()
        for _ in range(100)
    }
    link_ids = {
        create_principal_identity_link_id()
        for _ in range(100)
    }

    assert len(provider_ids) == 100
    assert len(link_ids) == 100
    assert all(
        value.startswith("idp_")
        for value in provider_ids
    )
    assert all(
        value.startswith("pil_")
        for value in link_ids
    )
