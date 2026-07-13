from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from execution_evidence.models import ExecutionEvidenceItem


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
        title=_first_line(message),
        description=message,
        url=_required_text(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "author_login": _optional_text(author.get("login")),
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
        title=title,
        description=_optional_text(payload.get("body")),
        url=_required_text(payload, "html_url"),
        occurred_at=merged_at or created_at,
        metadata={
            "state": _optional_text(payload.get("state")),
            "merged": bool(payload.get("merged_at")),
            "draft": bool(payload.get("draft", False)),
            "base_branch": _optional_text(
                _nested_value(payload, "base", "ref")
            ),
            "head_branch": _optional_text(
                _nested_value(payload, "head", "ref")
            ),
            "labels": [
                str(label.get("name"))
                for label in labels
                if isinstance(label, dict)
                and label.get("name")
            ],
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
        title=name or tag_name,
        description=_optional_text(payload.get("body")),
        url=_required_text(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "tag_name": tag_name,
            "target_commitish": _optional_text(
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
        title=name,
        description=_optional_text(
            payload.get("display_title")
        ),
        url=_required_text(payload, "html_url"),
        occurred_at=occurred_at,
        metadata={
            "status": _optional_text(payload.get("status")),
            "conclusion": _optional_text(
                payload.get("conclusion")
            ),
            "event": _optional_text(payload.get("event")),
            "branch": _optional_text(payload.get("head_branch")),
            "head_sha": _optional_text(payload.get("head_sha")),
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

    if value is None or not str(value).strip():
        raise GitHubPayloadError(
            f"GitHub payload field '{key}' must be non-empty."
        )

    return str(value).strip()


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
    return value.splitlines()[0].strip()


def _optional_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None
