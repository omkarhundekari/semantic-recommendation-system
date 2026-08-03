from datetime import datetime, timedelta, timezone

import pytest

from execution_evidence.github_webhook_credential_authority import (
    GitHubWebhookCredentialAuthority,
    create_github_webhook_credential_authority_id,
)


UTC = timezone.utc
NOW = datetime(
    2026,
    8,
    3,
    20,
    0,
    tzinfo=UTC,
)

CREDENTIAL_ID = (
    "gwc_123e4567-e89b-42d3-a456-426614174000"
)
AUTHORITY_ID = (
    "gwa_123e4567-e89b-42d3-a456-426614174000"
)


def _authority(
    **overrides,
) -> GitHubWebhookCredentialAuthority:
    values = {
        "github_webhook_credential_authority_id": (
            AUTHORITY_ID
        ),
        "github_webhook_credential_id": (
            CREDENTIAL_ID
        ),
        "repository_id": "123",
        "created_at": NOW,
        "retired_at": None,
        "retired_reason": None,
    }
    values.update(overrides)

    return GitHubWebhookCredentialAuthority(
        **values
    )


def test_authority_is_immutable():
    authority = _authority()

    with pytest.raises(Exception):
        authority.repository_id = "456"


def test_authority_accepts_current_state():
    authority = _authority()

    assert authority.repository_id == "123"
    assert authority.retired_at is None


def test_authority_accepts_retired_history():
    authority = _authority(
        retired_at=NOW + timedelta(days=1),
        retired_reason="rotated",
    )

    assert authority.retired_reason == "rotated"


@pytest.mark.parametrize(
    "repository_id",
    [
        "",
        " 123",
        "123 ",
        "00123",
        "0",
        "-1",
        "１２３",
        "abc",
    ],
)
def test_repository_id_requires_canonical_positive_ascii_integer(
    repository_id,
):
    with pytest.raises(ValueError):
        _authority(
            repository_id=repository_id
        )


def test_authority_requires_timezone():
    with pytest.raises(ValueError):
        _authority(
            created_at=NOW.replace(
                tzinfo=None
            )
        )


def test_current_authority_rejects_retired_reason():
    with pytest.raises(ValueError):
        _authority(
            retired_reason="rotated"
        )


def test_retired_authority_requires_reason():
    with pytest.raises(ValueError):
        _authority(
            retired_at=NOW + timedelta(days=1)
        )


def test_retired_at_cannot_precede_created_at():
    with pytest.raises(ValueError):
        _authority(
            retired_at=NOW - timedelta(seconds=1),
            retired_reason="invalid",
        )


def test_generated_authority_ids_are_distinct():
    first = (
        create_github_webhook_credential_authority_id()
    )
    second = (
        create_github_webhook_credential_authority_id()
    )

    assert first.startswith("gwa_")
    assert second.startswith("gwa_")
    assert first != second
