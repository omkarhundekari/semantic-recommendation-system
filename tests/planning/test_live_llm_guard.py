import pytest

from planning.live_llm_guard import require_live_openai_access


def test_guard_requires_explicit_cli_flag(monkeypatch):
    monkeypatch.setenv("PLANNING_PROVIDER", "openai")
    monkeypatch.setenv("PLANNING_LLM_ENABLED", "true")

    with pytest.raises(RuntimeError, match="--allow-live-llm"):
        require_live_openai_access(
            provider_name="openai",
            allow_live_llm=False,
        )


def test_guard_blocks_mock_environment(monkeypatch):
    monkeypatch.setenv("PLANNING_PROVIDER", "mock")
    monkeypatch.setenv("PLANNING_LLM_ENABLED", "false")

    with pytest.raises(RuntimeError, match="PLANNING_PROVIDER=openai"):
        require_live_openai_access(
            provider_name="openai",
            allow_live_llm=True,
        )


def test_guard_allows_only_fully_explicit_openai_access(monkeypatch):
    monkeypatch.setenv("PLANNING_PROVIDER", "openai")
    monkeypatch.setenv("PLANNING_LLM_ENABLED", "true")

    require_live_openai_access(
        provider_name="openai",
        allow_live_llm=True,
    )