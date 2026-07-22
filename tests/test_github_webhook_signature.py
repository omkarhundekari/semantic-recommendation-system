import hashlib
import hmac

import pytest

from execution_evidence.github_webhook_signature import (
    GitHubWebhookSignatureError,
    verify_github_webhook_signature,
)


SECRET = b"super-secret"
RAW_BODY = b'{"action":"completed"}'


def _signature(
    *,
    secret: bytes = SECRET,
    body: bytes = RAW_BODY,
) -> str:
    digest = hmac.new(
        secret,
        body,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def test_verify_github_webhook_signature_accepts_valid_signature():
    verify_github_webhook_signature(
        secret=SECRET,
        raw_body=RAW_BODY,
        signature_header=_signature(),
    )


def test_verify_github_webhook_signature_rejects_missing_signature():
    with pytest.raises(
        GitHubWebhookSignatureError,
        match="required",
    ):
        verify_github_webhook_signature(
            secret=SECRET,
            raw_body=RAW_BODY,
            signature_header=None,
        )


@pytest.mark.parametrize(
    "signature_header",
    [
        "",
        " ",
        "sha1=abc",
        "sha256",
        "sha256=",
        "sha256=not-hex",
        "sha256=" + ("a" * 63),
        "sha256=" + ("a" * 65),
    ],
)
def test_verify_github_webhook_signature_rejects_malformed_signature(
    signature_header,
):
    with pytest.raises(GitHubWebhookSignatureError):
        verify_github_webhook_signature(
            secret=SECRET,
            raw_body=RAW_BODY,
            signature_header=signature_header,
        )


def test_verify_github_webhook_signature_rejects_wrong_secret():
    with pytest.raises(
        GitHubWebhookSignatureError,
        match="verification failed",
    ):
        verify_github_webhook_signature(
            secret=b"wrong-secret",
            raw_body=RAW_BODY,
            signature_header=_signature(),
        )


def test_verify_github_webhook_signature_rejects_modified_body():
    with pytest.raises(
        GitHubWebhookSignatureError,
        match="verification failed",
    ):
        verify_github_webhook_signature(
            secret=SECRET,
            raw_body=b'{"action":"requested"}',
            signature_header=_signature(),
        )


@pytest.mark.parametrize(
    "secret",
    [
        b"",
        bytearray(b"secret"),
        "secret",
        None,
    ],
)
def test_verify_github_webhook_signature_rejects_invalid_secret(
    secret,
):
    with pytest.raises(GitHubWebhookSignatureError):
        verify_github_webhook_signature(
            secret=secret,
            raw_body=RAW_BODY,
            signature_header=_signature(),
        )


@pytest.mark.parametrize(
    "raw_body",
    [
        bytearray(RAW_BODY),
        '{"action":"completed"}',
        None,
    ],
)
def test_verify_github_webhook_signature_requires_raw_bytes(
    raw_body,
):
    with pytest.raises(GitHubWebhookSignatureError):
        verify_github_webhook_signature(
            secret=SECRET,
            raw_body=raw_body,
            signature_header=_signature(),
        )
