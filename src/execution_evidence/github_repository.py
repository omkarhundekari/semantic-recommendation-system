from __future__ import annotations

import re
from urllib.parse import urlparse

from execution_evidence.models import GitHubRepositoryReference


_GITHUB_PATH_PATTERN = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repository>[A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)

_GITHUB_SCP_PATTERN = re.compile(
    r"^git@github\.com:"
    r"(?P<owner>[A-Za-z0-9_.-]+)/"
    r"(?P<repository>[A-Za-z0-9_.-]+?)(?:\.git)?$"
)


def parse_github_repository_url(
    value: str,
) -> GitHubRepositoryReference:
    raw_value = value.strip()

    if not raw_value:
        raise ValueError("GitHub repository URL must be non-empty.")

    scp_match = _GITHUB_SCP_PATTERN.fullmatch(raw_value)

    if scp_match:
        return _build_reference(
            owner=scp_match.group("owner"),
            repository=scp_match.group("repository"),
        )

    parsed = urlparse(raw_value)

    if parsed.scheme not in {"http", "https", "ssh"}:
        raise ValueError(
            "GitHub repository URL must use HTTP, HTTPS, SSH, "
            "or git@github.com syntax."
        )

    hostname = (parsed.hostname or "").lower()

    if hostname != "github.com":
        raise ValueError("Only github.com repositories are supported.")

    normalized_path = parsed.path.strip("/")
    path_match = _GITHUB_PATH_PATTERN.fullmatch(normalized_path)

    if not path_match:
        raise ValueError(
            "GitHub repository URL must identify exactly one "
            "owner and repository."
        )

    return _build_reference(
        owner=path_match.group("owner"),
        repository=path_match.group("repository"),
    )


def _build_reference(
    *,
    owner: str,
    repository: str,
) -> GitHubRepositoryReference:
    normalized_repository = repository.removesuffix(".git")

    return GitHubRepositoryReference(
        owner=owner,
        repository=normalized_repository,
        canonical_url=(
            f"https://github.com/{owner}/{normalized_repository}"
        ),
    )
