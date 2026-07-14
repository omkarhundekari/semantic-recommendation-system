from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from execution_evidence.models import ExecutionEvidenceItem


MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 20_000
MAX_METADATA_TEXT_LENGTH = 500
MAX_LABEL_COUNT = 50
MAX_LABEL_LENGTH = 100


class GitHubPayloadError(ValueError):
    pass


def normalize_commit(
    *,
    repository_full_name: str,
    payload: Dict[str, Any],
    observed_at: datetime,
) -> ExecutionEvidenceItem:
    sha = _required_text(payload, "sha")
    commit = _required_mapping(payload, "commit")
    message = _required_text(commit, "message")

    occurred_at = _first_datetime(
        _nested_value(commit, "author", "date"),
        _nested_value(commit, "committer", "date"),
    )

    author = payload.get("author") or {}
    stats = payload.get("stats") or {}

    return ExecutionEvidenceItem(
        repository_full_name=repository_full_name,
        evidence_type="commit",
        external_id=sha,
        title=_bounded_title(_first_line(message)),
        description=_bounded_description(message),
        url=_required_github_url(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "author_login": _bounded_metadata_text(author.get("login")),
            "additions": _optional_int(stats.get("additions")),
            "deletions": _optional_int(stats.get("deletions")),
            "changed_files": _optional_int(
                payload.get("files")
                and len(payload["files"])
            ),
        },
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


def normalize_pull_request(
    *,
    repository_full_name: str,
    payload: Dict[str, Any],
    observed_at: datetime,
) -> ExecutionEvidenceItem:
    number = _required_value(payload, "number")
    title = _required_text(payload, "title")
    created_at = _parse_datetime(
        _required_text(payload, "created_at")
    )

    merged_at = _optional_datetime(payload.get("merged_at"))
    labels = payload.get("labels") or []

    return ExecutionEvidenceItem(
        repository_full_name=repository_full_name,
        evidence_type="pull_request",
        external_id=str(number),
        title=_bounded_title(title),
        description=_bounded_description(
            _optional_text(payload.get("body"))
        ),
        url=_required_github_url(payload, "html_url"),
        occurred_at=merged_at or created_at,
        metadata={
            "state": _bounded_metadata_text(payload.get("state")),
            "merged": bool(payload.get("merged_at")),
            "draft": bool(payload.get("draft", False)),
            "base_branch": _bounded_metadata_text(
                _nested_value(payload, "base", "ref")
            ),
            "head_branch": _bounded_metadata_text(
                _nested_value(payload, "head", "ref")
            ),
            "labels": _normalized_labels(labels),
            "additions": _optional_int(payload.get("additions")),
            "deletions": _optional_int(payload.get("deletions")),
            "changed_files": _optional_int(
                payload.get("changed_files")
            ),
        },
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


def normalize_release(
    *,
    repository_full_name: str,
    payload: Dict[str, Any],
    observed_at: datetime,
) -> ExecutionEvidenceItem:
    release_id = _required_value(payload, "id")
    tag_name = _required_text(payload, "tag_name")

    occurred_at = _first_datetime(
        payload.get("published_at"),
        payload.get("created_at"),
    )

    name = _optional_text(payload.get("name"))

    return ExecutionEvidenceItem(
        repository_full_name=repository_full_name,
        evidence_type="release",
        external_id=str(release_id),
        title=_bounded_title(name or tag_name),
        description=_bounded_description(
            _optional_text(payload.get("body"))
        ),
        url=_required_github_url(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "tag_name": tag_name,
            "target_commitish": _bounded_metadata_text(
                payload.get("target_commitish")
            ),
            "draft": bool(payload.get("draft", False)),
            "prerelease": bool(payload.get("prerelease", False)),
        },
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


def normalize_workflow_run(
    *,
    repository_full_name: str,
    payload: Dict[str, Any],
    observed_at: datetime,
) -> ExecutionEvidenceItem:
    run_id = _required_value(payload, "id")
    name = _required_text(payload, "name")

    occurred_at = _first_datetime(
        payload.get("run_started_at"),
        payload.get("created_at"),
    )

    return ExecutionEvidenceItem(
        repository_full_name=repository_full_name,
        evidence_type="workflow_run",
        external_id=str(run_id),
        title=_bounded_title(name),
        description=_bounded_description(
            _optional_text(
                payload.get("display_title")
            )
        ),
        url=_required_github_url(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "status": _bounded_metadata_text(payload.get("status")),
            "conclusion": _bounded_metadata_text(
                payload.get("conclusion")
            ),
            "event": _bounded_metadata_text(payload.get("event")),
            "branch": _bounded_metadata_text(payload.get("head_branch")),
            "head_sha": _bounded_metadata_text(payload.get("head_sha")),
            "run_number": _optional_int(
                payload.get("run_number")
            ),
            "attempt": _optional_int(
                payload.get("run_attempt")
            ),
        },
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )


def normalize_many(
    *,
    repository_full_name: str,
    evidence_type: str,
    payloads: Iterable[Dict[str, Any]],
    observed_at: datetime,
) -> List[ExecutionEvidenceItem]:
    normalizers = {
        "commit": normalize_commit,
        "pull_request": normalize_pull_request,
        "release": normalize_release,
        "workflow_run": normalize_workflow_run,
    }

    normalizer = normalizers.get(evidence_type)

    if normalizer is None:
        raise GitHubPayloadError(
            f"Unsupported GitHub evidence type: {evidence_type}"
        )

    return [
        normalizer(
            repository_full_name=repository_full_name,
            payload=payload,
            observed_at=observed_at,
        )
        for payload in payloads
    ]


def _required_mapping(
    payload: Dict[str, Any],
    key: str,
) -> Dict[str, Any]:
    value = payload.get(key)

    if not isinstance(value, dict):
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' must be an object."
        )

    return value


def _required_text(
    payload: Dict[str, Any],
    key: str,
) -> str:
    value = payload.get(key)

    if value is None:
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' must be non-empty."
        )

    normalized = _clean_text(value)

    if not normalized:
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' must be non-empty."
        )

    return normalized


def _required_github_url(
    payload: Dict[str, Any],
    key: str,
) -> str:
    value = _required_text(payload, key)
    parsed = urlparse(value)

    if (
        parsed.scheme.lower() != "https"
        or (parsed.hostname or "").lower() != "github.com"
        or not parsed.path
    ):
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' must be an "
            "https://github.com URL."
        )

    if parsed.username or parsed.password or parsed.port:
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' contains "
            "unsupported URL authority components."
        )

    return value


def _required_value(
    payload: Dict[str, Any],
    key: str,
) -> Any:
    value = payload.get(key)

    if value is None or value == "":
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' is required."
        )

    return value


def _nested_value(
    payload: Dict[str, Any],
    *keys: str,
) -> Any:
    current: Any = payload

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def _first_datetime(*values: Any) -> datetime:
    for value in values:
        parsed = _optional_datetime(value)

        if parsed is not None:
            return parsed

    raise GitHubPayloadError(
        "GitHub payload does not contain a valid event timestamp."
    )


def _optional_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None

    return _parse_datetime(str(value))


def _parse_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise GitHubPayloadError(
            f"Invalid GitHub timestamp: {value}"
        ) from error

    if parsed.tzinfo is None:
        raise GitHubPayloadError(
            "GitHub timestamps must include a timezone."
        )

    return parsed


def _first_line(value: str) -> str:
    lines = _clean_text(value).splitlines()

    for line in lines:
        if line.strip():
            return line.strip()

    return ""


def _optional_text(value: Any) -> str:
    if value is None:
        return ""

    return _clean_text(value)


def _clean_text(value: Any) -> str:
    text = str(value).replace("\r\n", "\n").replace(
        "\r",
        "\n",
    )

    cleaned = "".join(
        character
        for character in text
        if (
            character in {"\n", "\t"}
            or ord(character) >= 32
            and ord(character) != 127
        )
    )

    return cleaned.strip()


def _truncate_text(
    value: str,
    maximum_length: int,
) -> str:
    if len(value) <= maximum_length:
        return value

    return value[:maximum_length]


def _bounded_title(value: str) -> str:
    title = _truncate_text(
        _clean_text(value),
        MAX_TITLE_LENGTH,
    ).strip()

    if not title:
        raise GitHubPayloadError(
            "Normalized GitHub evidence title must be non-empty."
        )

    return title


def _bounded_description(value: str) -> str:
    return _truncate_text(
        _clean_text(value),
        MAX_DESCRIPTION_LENGTH,
    )


def _bounded_metadata_text(value: Any) -> str:
    return _truncate_text(
        _optional_text(value),
        MAX_METADATA_TEXT_LENGTH,
    )


def _normalized_labels(
    labels: Any,
) -> List[str]:
    if not isinstance(labels, list):
        return []

    normalized: List[str] = []

    for label in labels:
        if len(normalized) >= MAX_LABEL_COUNT:
            break

        if not isinstance(label, dict):
            continue

        name = _truncate_text(
            _optional_text(label.get("name")),
            MAX_LABEL_LENGTH,
        )

        if name:
            normalized.append(name)

    return normalized


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None
