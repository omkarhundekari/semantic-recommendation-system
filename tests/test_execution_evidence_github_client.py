from typing import Any, Dict, List, Optional

import pytest

from execution_evidence.github_client import (
    GitHubClientError,
    GitHubExecutionEvidenceClient,
)
from execution_evidence.github_repository import (
    parse_github_repository_url,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: Any = None,
        headers: Optional[Dict[str, str]] = None,
        json_error: bool = False,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self._json_error = json_error

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("Invalid JSON.")

        return self._payload


class FakeSession:
    def __init__(
        self,
        responses: List[FakeResponse],
    ) -> None:
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]],
        timeout: int,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "params": params,
                "timeout": timeout,
            }
        )

        if not self._responses:
            raise AssertionError("No fake response remains.")

        return self._responses.pop(0)


REFERENCE = parse_github_repository_url(
    "https://github.com/Owner/Repository"
)


def test_fetch_commits_uses_read_only_headers_and_parameters():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload=[{"sha": "abc123"}],
                headers={
                    "ETag": '"commit-etag"',
                    "X-RateLimit-Remaining": "4998",
                    "X-RateLimit-Reset": "1783900000",
                    "X-RateLimit-Limit": "5000",
                    "X-RateLimit-Resource": "core",
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
        token="test-token",
        timeout_seconds=12,
    )

    result = client.fetch_commits(
        REFERENCE,
        since="2026-07-01T00:00:00Z",
    )

    assert result.payloads == [{"sha": "abc123"}]
    assert result.etag == '"commit-etag"'
    assert result.pages_fetched == 1
    assert result.not_modified is False
    assert result.rate_limit.remaining == 4998
    assert result.rate_limit.limit == 5000
    assert result.rate_limit.resource == "core"

    call = session.calls[0]

    assert call["url"].endswith(
        "/repos/Owner/Repository/commits"
    )
    assert call["params"] == {
        "per_page": 100,
        "since": "2026-07-01T00:00:00Z",
    }
    assert call["timeout"] == 12
    assert call["headers"]["Authorization"] == (
        "Bearer test-token"
    )
    assert call["headers"]["Accept"] == (
        "application/vnd.github+json"
    )


def test_conditional_request_handles_not_modified():
    session = FakeSession(
        [
            FakeResponse(
                status_code=304,
                headers={
                    "ETag": '"repo-etag"',
                    "X-RateLimit-Remaining": "4999",
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    result = client.fetch_repository(
        REFERENCE,
        etag='"repo-etag"',
    )

    assert result.payloads == []
    assert result.not_modified is True
    assert result.etag == '"repo-etag"'
    assert result.pages_fetched == 0
    assert session.calls[0]["headers"]["If-None-Match"] == (
        '"repo-etag"'
    )


def test_fetch_pull_requests_follows_next_page_link():
    next_url = (
        "https://api.github.com/repositories/1/pulls"
        "?page=2&per_page=100"
    )

    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload=[{"number": 1}],
                headers={
                    "ETag": '"pull-etag"',
                    "Link": (
                        f'<{next_url}>; rel="next", '
                        '<https://api.github.com/final>; rel="last"'
                    ),
                },
            ),
            FakeResponse(
                status_code=200,
                payload=[{"number": 2}],
            ),
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    result = client.fetch_pull_requests(REFERENCE)

    assert result.payloads == [
        {"number": 1},
        {"number": 2},
    ]
    assert result.pages_fetched == 2
    assert result.etag == '"pull-etag"'

    assert session.calls[0]["params"]["state"] == "all"
    assert session.calls[1]["url"] == next_url
    assert session.calls[1]["params"] is None


def test_workflow_runs_extract_nested_collection():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload={
                    "total_count": 2,
                    "workflow_runs": [
                        {"id": 10},
                        {"id": 11},
                    ],
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    result = client.fetch_workflow_runs(REFERENCE)

    assert result.payloads == [
        {"id": 10},
        {"id": 11},
    ]


def test_repository_fetch_wraps_single_object():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload={
                    "id": 1,
                    "full_name": "Owner/Repository",
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    result = client.fetch_repository(REFERENCE)

    assert result.payloads == [
        {
            "id": 1,
            "full_name": "Owner/Repository",
        }
    ]


def test_client_exposes_rate_limit_on_api_error():
    session = FakeSession(
        [
            FakeResponse(
                status_code=403,
                payload={
                    "message": "API rate limit exceeded",
                },
                headers={
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "1783900000",
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    with pytest.raises(
        GitHubClientError,
        match="API rate limit exceeded",
    ) as captured:
        client.fetch_releases(REFERENCE)

    assert captured.value.status_code == 403
    assert captured.value.rate_limit.remaining == 0
    assert (
        captured.value.rate_limit.reset_epoch
        == 1783900000
    )


def test_client_rejects_invalid_json():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                json_error=True,
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    with pytest.raises(
        GitHubClientError,
        match="invalid JSON",
    ):
        client.fetch_commits(REFERENCE)


def test_workflow_response_requires_collection_list():
    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload={
                    "workflow_runs": {
                        "id": 10,
                    },
                },
            )
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
    )

    with pytest.raises(
        GitHubClientError,
        match="workflow_runs.*must be a list",
    ):
        client.fetch_workflow_runs(REFERENCE)


def test_client_stops_at_configured_page_limit():
    next_url = "https://api.github.com/page/2"

    session = FakeSession(
        [
            FakeResponse(
                status_code=200,
                payload=[{"sha": "first"}],
                headers={
                    "Link": f'<{next_url}>; rel="next"',
                },
            ),
            FakeResponse(
                status_code=200,
                payload=[{"sha": "second"}],
            ),
        ]
    )

    client = GitHubExecutionEvidenceClient(
        session=session,
        max_pages=1,
    )

    result = client.fetch_commits(REFERENCE)

    assert result.payloads == [{"sha": "first"}]
    assert result.pages_fetched == 1
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    ("timeout_seconds", "max_pages"),
    [
        (0, 10),
        (20, 0),
    ],
)
def test_client_rejects_invalid_configuration(
    timeout_seconds,
    max_pages,
):
    with pytest.raises(ValueError):
        GitHubExecutionEvidenceClient(
            timeout_seconds=timeout_seconds,
            max_pages=max_pages,
        )
