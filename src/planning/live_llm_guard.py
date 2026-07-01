import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(
    dotenv_path=Path(__file__).resolve().parents[2] / ".env",
    override=False,
)


def require_live_openai_access(
    provider_name: str,
    allow_live_llm: bool,
) -> None:
    if provider_name != "openai":
        raise RuntimeError(
            "Live LLM access requires provider_name='openai'."
        )

    if not allow_live_llm:
        raise RuntimeError(
            "Live LLM access requires the --allow-live-llm flag."
        )

    configured_provider = os.getenv(
        "PLANNING_PROVIDER",
        "",
    ).strip().lower()
    llm_enabled = os.getenv(
        "PLANNING_LLM_ENABLED",
        "",
    ).strip().lower()

    if configured_provider != "openai":
        raise RuntimeError(
            "Set PLANNING_PROVIDER=openai in .env before a live run."
        )

    if llm_enabled != "true":
        raise RuntimeError(
            "Set PLANNING_LLM_ENABLED=true in .env before a live run."
        )
