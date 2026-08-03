import pytest

from execution_evidence.environment_github_webhook_secret_resolver import (
    EnvironmentGitHubWebhookSecretResolver,
)
from execution_evidence.github_webhook_secret_resolver import (
    GitHubWebhookSecretNotFoundError,
)


SECRET_REF = "SOLVYN_GITHUB_WEBHOOK_TEST_SECRET"


def test_resolver_returns_secret_bytes(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        SECRET_REF,
        "super-secret-value",
    )

    resolver = EnvironmentGitHubWebhookSecretResolver()

    assert resolver.resolve(
        SECRET_REF
    ) == b"super-secret-value"


def test_resolver_does_not_trim_reference(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        SECRET_REF,
        "super-secret-value",
    )

    resolver = EnvironmentGitHubWebhookSecretResolver()

    with pytest.raises(ValueError):
        resolver.resolve(
            f" {SECRET_REF} "
        )


def test_resolver_rejects_non_text_reference():
    resolver = EnvironmentGitHubWebhookSecretResolver()

    with pytest.raises(ValueError):
        resolver.resolve(123)


def test_resolver_missing_secret_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv(
        SECRET_REF,
        raising=False,
    )

    resolver = EnvironmentGitHubWebhookSecretResolver()

    with pytest.raises(
        GitHubWebhookSecretNotFoundError
    ):
        resolver.resolve(SECRET_REF)


def test_resolver_blank_secret_is_not_found(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        SECRET_REF,
        "",
    )

    resolver = EnvironmentGitHubWebhookSecretResolver()

    with pytest.raises(
        GitHubWebhookSecretNotFoundError
    ):
        resolver.resolve(SECRET_REF)


def test_resolver_preserves_secret_value_exactly(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        SECRET_REF,
        "  secret with spaces  ",
    )

    resolver = EnvironmentGitHubWebhookSecretResolver()

    assert resolver.resolve(
        SECRET_REF
    ) == b"  secret with spaces  "
