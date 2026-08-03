from __future__ import annotations

import os

from execution_evidence.github_webhook_secret_resolver import (
    GitHubWebhookSecretNotFoundError,
    GitHubWebhookSecretResolver,
)


class EnvironmentGitHubWebhookSecretResolver(
    GitHubWebhookSecretResolver
):
    def resolve(
        self,
        secret_ref: str,
    ) -> bytes:
        if not isinstance(secret_ref, str):
            raise ValueError(
                "GitHub webhook secret reference "
                "must be text."
            )

        if not secret_ref:
            raise ValueError(
                "GitHub webhook secret reference "
                "must be non-empty."
            )

        if secret_ref != secret_ref.strip():
            raise ValueError(
                "GitHub webhook secret reference "
                "must not contain surrounding whitespace."
            )

        value = os.getenv(secret_ref)

        if value is None or not value:
            raise GitHubWebhookSecretNotFoundError(
                "GitHub webhook secret could not "
                "be resolved."
            )

        return value.encode("utf-8")
