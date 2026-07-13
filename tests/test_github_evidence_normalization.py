from datetime import datetime

import pytest

from execution_evidence.github_normalization import (
    GitHubPayloadError,
    normalize_commit,
    normalize_many,
    normalize_pull_request,
    normalize_release,
    normalize_workflow_run,
)


REPOSITORY = "omkarhundekari/semantic-recommendation-system"
OBSERVED_AT = datetime.fromisoformat(
    "2026-07-13T12:00:00+00:00"
)


def test_normalize_commit_maps_stable_identity_and_metadata():
    item = normalize_commit(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "sha": "abc123",
            "html_url": (
                "https://github.com/omkarhundekari/"
                "semantic-recommendation-system/commit/abc123"
            ),
            "commit": {
                "message": (
                    "Add execution evidence normalizers\n\n"
                    "Normalize GitHub payloads."
                ),
                "author": {
                    "date": "2026-07-13T10:00:00Z",
                },
            },
            "author": {"login": "omkarhundekari"},
            "stats": {
                "additions": 120,
                "deletions": 4,
            },
            "files": [{}, {}, {}],
        },
    )

    assert item.evidence_type == "commit"
    assert item.external_id == "abc123"
    assert item.title == "Add execution evidence normalizers"
    assert item.metadata["author_login"] == "omkarhundekari"
    assert item.metadata["changed_files"] == 3
    assert item.evidence_key == (
        "github:"
        "omkarhundekari/semantic-recommendation-system:"
        "commit:"
        "abc123"
    )


def test_normalize_pull_request_prefers_merged_time():
    item = normalize_pull_request(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "number": 42,
            "title": "Add GitHub evidence ingestion",
            "body": "Introduces deterministic normalization.",
            "html_url": "https://github.com/owner/repo/pull/42",
            "state": "closed",
            "created_at": "2026-07-10T09:00:00Z",
            "merged_at": "2026-07-12T11:00:00Z",
            "draft": False,
            "base": {"ref": "main"},
            "head": {"ref": "feature/evidence"},
            "labels": [
                {"name": "backend"},
                {"name": "evidence"},
            ],
            "additions": 230,
            "deletions": 11,
            "changed_files": 6,
        },
    )

    assert item.external_id == "42"
    assert item.occurred_at == datetime.fromisoformat(
        "2026-07-12T11:00:00+00:00"
    )
    assert item.metadata["merged"] is True
    assert item.metadata["head_branch"] == "feature/evidence"
    assert item.metadata["labels"] == [
        "backend",
        "evidence",
    ]


def test_normalize_pull_request_uses_created_time_when_unmerged():
    item = normalize_pull_request(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "number": 43,
            "title": "Draft attribution rules",
            "html_url": "https://github.com/owner/repo/pull/43",
            "created_at": "2026-07-13T08:00:00Z",
            "merged_at": None,
            "state": "open",
        },
    )

    assert item.occurred_at == datetime.fromisoformat(
        "2026-07-13T08:00:00+00:00"
    )
    assert item.metadata["merged"] is False


def test_normalize_release_uses_database_id_for_identity():
    item = normalize_release(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "id": 9001,
            "tag_name": "v2.2.0",
            "name": "Execution Evidence Foundation",
            "body": "Adds evidence-grounding contracts.",
            "html_url": (
                "https://github.com/owner/repo/releases/tag/v2.2.0"
            ),
            "published_at": "2026-07-13T09:30:00Z",
            "created_at": "2026-07-13T09:00:00Z",
            "target_commitish": "main",
            "draft": False,
            "prerelease": False,
        },
    )

    assert item.external_id == "9001"
    assert item.title == "Execution Evidence Foundation"
    assert item.metadata["tag_name"] == "v2.2.0"
    assert item.occurred_at == datetime.fromisoformat(
        "2026-07-13T09:30:00+00:00"
    )


def test_normalize_release_falls_back_to_tag_as_title():
    item = normalize_release(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "id": 9002,
            "tag_name": "v2.2.1",
            "name": "",
            "html_url": (
                "https://github.com/owner/repo/releases/tag/v2.2.1"
            ),
            "created_at": "2026-07-13T10:00:00Z",
        },
    )

    assert item.title == "v2.2.1"


def test_normalize_workflow_run_captures_ci_result():
    item = normalize_workflow_run(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "id": 7001,
            "name": "Backend tests",
            "display_title": "Add execution evidence domain",
            "html_url": (
                "https://github.com/owner/repo/actions/runs/7001"
            ),
            "run_started_at": "2026-07-13T10:15:00Z",
            "created_at": "2026-07-13T10:14:00Z",
            "status": "completed",
            "conclusion": "success",
            "event": "push",
            "head_branch": "main",
            "head_sha": "abc123",
            "run_number": 91,
            "run_attempt": 1,
        },
    )

    assert item.external_id == "7001"
    assert item.metadata["conclusion"] == "success"
    assert item.metadata["head_sha"] == "abc123"
    assert item.metadata["run_number"] == 91


@pytest.mark.parametrize(
    ("normalizer", "payload"),
    [
        (
            normalize_commit,
            {
                "sha": "",
                "html_url": "https://github.com/owner/repo/commit/a",
                "commit": {
                    "message": "Message",
                    "author": {
                        "date": "2026-07-13T10:00:00Z",
                    },
                },
            },
        ),
        (
            normalize_pull_request,
            {
                "number": 1,
                "title": "",
                "html_url": "https://github.com/owner/repo/pull/1",
                "created_at": "2026-07-13T10:00:00Z",
            },
        ),
        (
            normalize_release,
            {
                "id": 1,
                "tag_name": "v1",
                "html_url": "https://github.com/owner/repo/releases/1",
            },
        ),
        (
            normalize_workflow_run,
            {
                "id": 1,
                "name": "Tests",
                "html_url": "https://github.com/owner/repo/actions/runs/1",
                "created_at": "not-a-date",
            },
        ),
    ],
)
def test_normalizers_reject_incomplete_or_invalid_payloads(
    normalizer,
    payload,
):
    with pytest.raises(GitHubPayloadError):
        normalizer(
            repository_full_name=REPOSITORY,
            payload=payload,
            observed_at=OBSERVED_AT,
        )


def test_refreshed_payload_preserves_evidence_identity():
    original = normalize_pull_request(
        repository_full_name=REPOSITORY,
        observed_at=OBSERVED_AT,
        payload={
            "number": 42,
            "title": "Initial title",
            "html_url": "https://github.com/owner/repo/pull/42",
            "created_at": "2026-07-10T09:00:00Z",
            "state": "open",
        },
    )

    refreshed = normalize_pull_request(
        repository_full_name=REPOSITORY,
        observed_at=datetime.fromisoformat(
            "2026-07-14T12:00:00+00:00"
        ),
        payload={
            "number": 42,
            "title": "Updated title",
            "html_url": "https://github.com/owner/repo/pull/42",
            "created_at": "2026-07-10T09:00:00Z",
            "merged_at": "2026-07-14T11:00:00Z",
            "state": "closed",
        },
    )

    assert original.evidence_key == refreshed.evidence_key
    assert original.title != refreshed.title
    assert refreshed.metadata["merged"] is True


def test_normalize_many_dispatches_requested_evidence_type():
    items = normalize_many(
        repository_full_name=REPOSITORY,
        evidence_type="workflow_run",
        observed_at=OBSERVED_AT,
        payloads=[
            {
                "id": 100,
                "name": "Tests",
                "html_url": (
                    "https://github.com/owner/repo/actions/runs/100"
                ),
                "created_at": "2026-07-13T10:00:00Z",
            },
            {
                "id": 101,
                "name": "Lint",
                "html_url": (
                    "https://github.com/owner/repo/actions/runs/101"
                ),
                "created_at": "2026-07-13T10:01:00Z",
            },
        ],
    )

    assert [item.external_id for item in items] == [
        "100",
        "101",
    ]


def test_normalize_many_rejects_unknown_type():
    with pytest.raises(
        GitHubPayloadError,
        match="Unsupported GitHub evidence type",
    ):
        normalize_many(
            repository_full_name=REPOSITORY,
            evidence_type="issue",
            observed_at=OBSERVED_AT,
            payloads=[],
        )
