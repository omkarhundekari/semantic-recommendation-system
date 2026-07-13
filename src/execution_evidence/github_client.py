from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field

from execution_evidence.github_repository import (
    GitHubRepositoryReference,
)


GITHUB_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 10


class GitHubRateLimit(BaseModel):
    remaining: Optional[int] = None
    reset_epoch: Optional[int] = None
    limit: Optional[int] = None
    resource: Optional[str] = None


class GitHubFetchResult(BaseModel):
    payloads: List[Dict[str, Any]] = Field(default_factory=list)
    etag: Optional[str] = None
    not_modified: bool = False
    pages_fetched: int = 0
    rate_limit: GitHubRateLimit = Field(
        default_factory=GitHubRateLimit
    )


class GitHubClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        rate_limit: Optional[GitHubRateLimit] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.rate_limit = rate_limit or GitHubRateLimit()


class GitHubExecutionEvidenceClient:
    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        token: Optional[str] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        max_pages: int = DEFAULT_MAX_PAGES,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "GitHub timeout must be greater than zero."
            )

        if max_pages <= 0:
            raise ValueError(
                "GitHub maximum page count must be greater than zero."
            )

        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds
        self._max_pages = max_pages
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "solvyn-execution-evidence",
        }

        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def fetch_repository(
        self,
        reference: GitHubRepositoryReference,
        *,
        etag: Optional[str] = None,
    ) -> GitHubFetchResult:
        return self._fetch_paginated(
            url=(
                f"{GITHUB_API_BASE}/repos/"
                f"{reference.owner}/{reference.repository}"
            ),
            params=None,
            etag=etag,
            collection_key=None,
        )

    def fetch_commits(
        self,
        reference: GitHubRepositoryReference,
        *,
        etag: Optional[str] = None,
        since: Optional[str] = None,
    ) -> GitHubFetchResult:
        params: Dict[str, Any] = {
            "per_page": DEFAULT_PAGE_SIZE,
        }

        if since:
            params["since"] = since

        return self._fetch_paginated(
            url=(
                f"{GITHUB_API_BASE}/repos/"
                f"{reference.owner}/{reference.repository}/commits"
            ),
            params=params,
            etag=etag,
            collection_key=None,
        )

    def fetch_pull_requests(
        self,
        reference: GitHubRepositoryReference,
        *,
        etag: Optional[str] = None,
    ) -> GitHubFetchResult:
        return self._fetch_paginated(
            url=(
                f"{GITHUB_API_BASE}/repos/"
                f"{reference.owner}/{reference.repository}/pulls"
            ),
            params={
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": DEFAULT_PAGE_SIZE,
            },
            etag=etag,
            collection_key=None,
        )

    def fetch_releases(
        self,
        reference: GitHubRepositoryReference,
        *,
        etag: Optional[str] = None,
    ) -> GitHubFetchResult:
        return self._fetch_paginated(
            url=(
                f"{GITHUB_API_BASE}/repos/"
                f"{reference.owner}/{reference.repository}/releases"
            ),
            params={
                "per_page": DEFAULT_PAGE_SIZE,
            },
            etag=etag,
            collection_key=None,
        )

    def fetch_workflow_runs(
        self,
        reference: GitHubRepositoryReference,
        *,
        etag: Optional[str] = None,
    ) -> GitHubFetchResult:
        return self._fetch_paginated(
            url=(
                f"{GITHUB_API_BASE}/repos/"
                f"{reference.owner}/{reference.repository}/actions/runs"
            ),
            params={
                "per_page": DEFAULT_PAGE_SIZE,
            },
            etag=etag,
            collection_key="workflow_runs",
        )

    def _fetch_paginated(
        self,
        *,
        url: str,
        params: Optional[Dict[str, Any]],
        etag: Optional[str],
        collection_key: Optional[str],
    ) -> GitHubFetchResult:
        request_headers = dict(self._headers)

        if etag:
            request_headers["If-None-Match"] = etag

        payloads: List[Dict[str, Any]] = []
        pages_fetched = 0
        current_url: Optional[str] = url
        current_params = params
        response_etag: Optional[str] = None
        latest_rate_limit = GitHubRateLimit()

        while current_url and pages_fetched < self._max_pages:
            response = self._session.get(
                current_url,
                headers=request_headers,
                params=current_params,
                timeout=self._timeout_seconds,
            )

            latest_rate_limit = _rate_limit_from_headers(
                response.headers
            )

            if response.status_code == 304:
                return GitHubFetchResult(
                    payloads=[],
                    etag=etag or response.headers.get("ETag"),
                    not_modified=True,
                    pages_fetched=pages_fetched,
                    rate_limit=latest_rate_limit,
                )

            if response.status_code != 200:
                raise GitHubClientError(
                    _error_message(response),
                    status_code=response.status_code,
                    rate_limit=latest_rate_limit,
                )

            pages_fetched += 1

            if pages_fetched == 1:
                response_etag = response.headers.get("ETag")

            response_payload = _response_json(response)

            if collection_key:
                page_items = response_payload.get(collection_key)

                if not isinstance(page_items, list):
                    raise GitHubClientError(
                        "GitHub response field "
                        f"'{collection_key}' must be a list.",
                        status_code=response.status_code,
                        rate_limit=latest_rate_limit,
                    )
            elif isinstance(response_payload, list):
                page_items = response_payload
            elif isinstance(response_payload, dict):
                page_items = [response_payload]
            else:
                raise GitHubClientError(
                    "GitHub response must be an object or list.",
                    status_code=response.status_code,
                    rate_limit=latest_rate_limit,
                )

            payloads.extend(
                item
                for item in page_items
                if isinstance(item, dict)
            )

            current_url = _next_link(
                response.headers.get("Link")
            )
            current_params = None

            # Conditional headers apply to the original resource.
            request_headers.pop("If-None-Match", None)

        return GitHubFetchResult(
            payloads=payloads,
            etag=response_etag,
            not_modified=False,
            pages_fetched=pages_fetched,
            rate_limit=latest_rate_limit,
        )


def _response_json(response: Any) -> Any:
    try:
        return response.json()
    except (TypeError, ValueError) as error:
        raise GitHubClientError(
            "GitHub returned invalid JSON.",
            status_code=response.status_code,
            rate_limit=_rate_limit_from_headers(
                response.headers
            ),
        ) from error


def _error_message(response: Any) -> str:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        payload = None

    if isinstance(payload, dict):
        message = str(payload.get("message", "")).strip()

        if message:
            return (
                f"GitHub API request failed with "
                f"status {response.status_code}: {message}"
            )

    return (
        f"GitHub API request failed with "
        f"status {response.status_code}."
    )


def _rate_limit_from_headers(
    headers: Dict[str, Any],
) -> GitHubRateLimit:
    return GitHubRateLimit(
        remaining=_optional_int(
            headers.get("X-RateLimit-Remaining")
        ),
        reset_epoch=_optional_int(
            headers.get("X-RateLimit-Reset")
        ),
        limit=_optional_int(
            headers.get("X-RateLimit-Limit")
        ),
        resource=_optional_text(
            headers.get("X-RateLimit-Resource")
        ),
    )


def _next_link(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None

    for entry in link_header.split(","):
        match = re.match(
            r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"',
            entry.strip(),
        )

        if match and match.group(2) == "next":
            return match.group(1)

    return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    return text or None
