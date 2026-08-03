from datetime import datetime, timedelta, timezone

import pytest

from execution_evidence.github_webhook_credential import (
    GitHubWebhookCredential,
    create_github_webhook_credential_id,
    create_github_webhook_endpoint_id,
)


UTC = timezone.utc
NOW = datetime(
    2026,
    8,
    3,
    12,
    0,
    tzinfo=UTC,
)

CREDENTIAL_ID = (
    "gwc_123e4567-e89b-42d3-a456-426614174000"
)
ENDPOINT_ID = (
    "gwe_123e4567-e89b-42d3-a456-426614174001"
)


def _credential(**changes):
    values = {
        "github_webhook_credential_id": CREDENTIAL_ID,
        "webhook_endpoint_id": ENDPOINT_ID,
        "installation_id": None,
        "secret_ref": "SOLVYN_GITHUB_WEBHOOK_A",
        "created_at": NOW,
        "retired_at": None,
        "retired_reason": None,
    }
    values.update(changes)

    return GitHubWebhookCredential(**values)


def test_credential_is_immutable():
    credential = _credential()

    with pytest.raises(Exception):
        credential.secret_ref = "changed"


def test_credential_accepts_current_state():
    credential = _credential()

    assert credential.retired_at is None
    assert credential.retired_reason is None


def test_credential_accepts_installation_provenance():
    credential = _credential(
        installation_id="123456"
    )

    assert credential.installation_id == "123456"


def test_credential_accepts_retired_history():
    credential = _credential(
        retired_at=NOW + timedelta(days=1),
        retired_reason="rotated",
    )

    assert credential.retired_reason == "rotated"


@pytest.mark.parametrize(
    "credential_id",
    [
        "credential",
        "gwc_not-a-uuid",
        "gwc_123e4567-e89b-12d3-a456-426614174000",
    ],
)
def test_credential_id_requires_canonical_gwc_uuid4(
    credential_id,
):
    with pytest.raises(ValueError):
        _credential(
            github_webhook_credential_id=credential_id
        )


@pytest.mark.parametrize(
    "endpoint_id",
    [
        "endpoint",
        "gwe_not-a-uuid",
        "gwe_123e4567-e89b-12d3-a456-426614174001",
    ],
)
def test_endpoint_id_requires_canonical_gwe_uuid4(
    endpoint_id,
):
    with pytest.raises(ValueError):
        _credential(
            webhook_endpoint_id=endpoint_id
        )


@pytest.mark.parametrize(
    "installation_id",
    [
        "",
        " 123",
        "123 ",
        "00123",
        "0",
        "-1",
        "1.0",
        "１２３",
    ],
)
def test_installation_id_requires_canonical_positive_ascii_integer(
    installation_id,
):
    with pytest.raises(ValueError):
        _credential(
            installation_id=installation_id
        )


def test_secret_ref_is_preserved_exactly():
    credential = _credential(
        secret_ref="vault://github/hook:A?version=7"
    )

    assert (
        credential.secret_ref
        == "vault://github/hook:A?version=7"
    )


@pytest.mark.parametrize(
    "secret_ref",
    [
        "",
        " ",
        " SECRET_REF",
        "SECRET_REF ",
        "\tSECRET_REF",
        "SECRET_REF\n",
    ],
)
def test_secret_ref_rejects_blank_or_surrounding_whitespace(
    secret_ref,
):
    with pytest.raises(ValueError):
        _credential(secret_ref=secret_ref)


def test_created_at_requires_timezone():
    with pytest.raises(ValueError):
        _credential(
            created_at=NOW.replace(tzinfo=None)
        )


def test_retired_at_requires_timezone():
    with pytest.raises(ValueError):
        _credential(
            retired_at=(
                NOW + timedelta(days=1)
            ).replace(tzinfo=None),
            retired_reason="rotated",
        )


def test_current_credential_rejects_retired_reason():
    with pytest.raises(ValueError):
        _credential(
            retired_reason="unexpected"
        )


def test_retired_credential_requires_reason():
    with pytest.raises(ValueError):
        _credential(
            retired_at=NOW + timedelta(days=1)
        )


def test_retired_reason_is_normalized():
    credential = _credential(
        retired_at=NOW + timedelta(days=1),
        retired_reason="  rotated  ",
    )

    assert credential.retired_reason == "rotated"


def test_blank_retired_reason_is_rejected():
    with pytest.raises(ValueError):
        _credential(
            retired_at=NOW + timedelta(days=1),
            retired_reason="   ",
        )


def test_retired_at_cannot_precede_created_at():
    with pytest.raises(ValueError):
        _credential(
            retired_at=NOW - timedelta(seconds=1),
            retired_reason="invalid",
        )


def test_generated_credential_ids_are_distinct():
    first = create_github_webhook_credential_id()
    second = create_github_webhook_credential_id()

    assert first != second
    assert first.startswith("gwc_")
    assert second.startswith("gwc_")


def test_generated_endpoint_ids_are_distinct():
    first = create_github_webhook_endpoint_id()
    second = create_github_webhook_endpoint_id()

    assert first != second
    assert first.startswith("gwe_")
    assert second.startswith("gwe_")
