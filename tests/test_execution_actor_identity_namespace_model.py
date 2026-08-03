from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from execution_evidence.execution_actor_identity_namespace import (
    ExecutionActorIdentityNamespace,
    create_execution_actor_namespace_id,
)


NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=timezone.utc,
)

NAMESPACE_ID = (
    "ean_11111111-1111-4111-8111-111111111111"
)

PROVIDER_ID = (
    "idp_22222222-2222-4222-8222-222222222222"
)


def _namespace(
    **overrides,
) -> ExecutionActorIdentityNamespace:
    values = {
        "execution_actor_namespace_id": (
            NAMESPACE_ID
        ),
        "source_provider": "github",
        "identity_provider_id": PROVIDER_ID,
        "issuer": "https://github.com",
        "created_at": NOW,
        "retired_at": None,
        "retired_reason": None,
    }
    values.update(overrides)

    return ExecutionActorIdentityNamespace(
        **values
    )


def test_namespace_is_immutable():
    namespace = _namespace()

    with pytest.raises(ValidationError):
        namespace.source_provider = "other"


def test_namespace_accepts_current_state():
    namespace = _namespace()

    assert namespace.source_provider == "github"
    assert namespace.retired_at is None
    assert namespace.retired_reason is None


def test_namespace_accepts_retired_history():
    retired_at = NOW + timedelta(days=1)

    namespace = _namespace(
        retired_at=retired_at,
        retired_reason="configuration retired",
    )

    assert namespace.retired_at == retired_at
    assert namespace.retired_reason == (
        "configuration retired"
    )


def test_namespace_rejects_bad_namespace_prefix():
    with pytest.raises(
        ValidationError,
        match="must start",
    ):
        _namespace(
            execution_actor_namespace_id=(
                "namespace_11111111-1111-4111-"
                "8111-111111111111"
            )
        )


def test_namespace_rejects_noncanonical_namespace_uuid():
    with pytest.raises(
        ValidationError,
        match="canonical UUID4",
    ):
        _namespace(
            execution_actor_namespace_id=(
                "ean_00000000-0000-0000-0000-"
                "000000000000"
            )
        )


def test_namespace_rejects_bad_provider_id():
    with pytest.raises(
        ValidationError,
        match="Identity provider ID",
    ):
        _namespace(
            identity_provider_id="provider-test"
        )


def test_namespace_preserves_exact_source_provider():
    namespace = _namespace(
        source_provider="GitHub"
    )

    assert namespace.source_provider == "GitHub"


def test_namespace_rejects_source_provider_whitespace():
    with pytest.raises(
        ValidationError,
        match="surrounding whitespace",
    ):
        _namespace(
            source_provider=" github "
        )


def test_namespace_preserves_exact_issuer():
    namespace = _namespace(
        issuer="https://issuer.example/"
    )

    assert namespace.issuer == (
        "https://issuer.example/"
    )


def test_namespace_rejects_issuer_whitespace():
    with pytest.raises(
        ValidationError,
        match="surrounding whitespace",
    ):
        _namespace(
            issuer=" https://issuer.example "
        )


def test_namespace_requires_created_at_timezone():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _namespace(
            created_at=datetime(
                2026,
                8,
                3,
                12,
                0,
            )
        )


def test_namespace_requires_retired_at_timezone():
    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        _namespace(
            retired_at=datetime(
                2026,
                8,
                4,
                12,
                0,
            ),
            retired_reason="retired",
        )


def test_current_namespace_rejects_retired_reason():
    with pytest.raises(
        ValidationError,
        match="cannot contain",
    ):
        _namespace(
            retired_reason="retired"
        )


def test_retired_namespace_requires_reason():
    with pytest.raises(
        ValidationError,
        match="require a retirement reason",
    ):
        _namespace(
            retired_at=NOW + timedelta(days=1)
        )


def test_retired_reason_is_normalized():
    namespace = _namespace(
        retired_at=NOW + timedelta(days=1),
        retired_reason="  wrong mapping  ",
    )

    assert namespace.retired_reason == (
        "wrong mapping"
    )


def test_blank_retired_reason_is_rejected():
    with pytest.raises(
        ValidationError,
        match="require a retirement reason",
    ):
        _namespace(
            retired_at=NOW + timedelta(days=1),
            retired_reason="   ",
        )


def test_retired_at_cannot_precede_created_at():
    with pytest.raises(
        ValidationError,
        match="cannot precede",
    ):
        _namespace(
            retired_at=NOW - timedelta(seconds=1),
            retired_reason="retired",
        )


def test_generated_namespace_ids_are_distinct():
    first = create_execution_actor_namespace_id()
    second = create_execution_actor_namespace_id()

    assert first != second

    ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=first,
        source_provider="github",
        identity_provider_id=PROVIDER_ID,
        issuer="https://github.com",
        created_at=NOW,
    )

    ExecutionActorIdentityNamespace(
        execution_actor_namespace_id=second,
        source_provider="gitlab",
        identity_provider_id=PROVIDER_ID,
        issuer="https://github.com",
        created_at=NOW,
    )
