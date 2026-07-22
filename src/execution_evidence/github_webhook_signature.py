import hashlib
import hmac
import re
from typing import Optional


_SIGNATURE_PATTERN = re.compile(
    r"^sha256=([0-9a-fA-F]{64})$"
)


class GitHubWebhookSignatureError(ValueError):
    pass


def verify_github_webhook_signature(
    *,
    secret: bytes,
    raw_body: bytes,
    signature_header: Optional[str],
) -> None:
    if not isinstance(secret, bytes) or not secret:
        raise GitHubWebhookSignatureError(
            "GitHub webhook secret must be non-empty bytes."
        )

    if not isinstance(raw_body, bytes):
        raise GitHubWebhookSignatureError(
            "GitHub webhook raw body must be bytes."
        )

    if signature_header is None:
        raise GitHubWebhookSignatureError(
            "GitHub webhook signature is required."
        )

    if not isinstance(signature_header, str):
        raise GitHubWebhookSignatureError(
            "GitHub webhook signature must be a string."
        )

    match = _SIGNATURE_PATTERN.fullmatch(
        signature_header
    )

    if match is None:
        raise GitHubWebhookSignatureError(
            "GitHub webhook signature is malformed."
        )

    received_digest = match.group(1).lower()

    expected_digest = hmac.new(
        secret,
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        received_digest,
        expected_digest,
    ):
        raise GitHubWebhookSignatureError(
            "GitHub webhook signature verification failed."
        )
