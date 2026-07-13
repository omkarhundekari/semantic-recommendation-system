from datetime import datetime

from execution_evidence.merge import merge_execution_evidence
from execution_evidence.models import ExecutionEvidenceItem


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _commit(
    *,
    sha: str,
    title: str,
    first_seen_at: str,
    last_seen_at: str,
) -> ExecutionEvidenceItem:
    return ExecutionEvidenceItem(
        repository_full_name="omkarhundekari/solvyn",
        evidence_type="commit",
        external_id=sha,
        title=title,
        url=(
            "https://github.com/"
            f"omkarhundekari/solvyn/commit/{sha}"
        ),
        occurred_at=_timestamp("2026-07-13T00:00:00Z"),
        first_seen_at=_timestamp(first_seen_at),
        last_seen_at=_timestamp(last_seen_at),
    )


def test_merge_is_idempotent():
    item = _commit(
        sha="abc123",
        title="Add evidence models",
        first_seen_at="2026-07-13T00:01:00Z",
        last_seen_at="2026-07-13T00:01:00Z",
    )

    first_merge = merge_execution_evidence([], [item])
    second_merge = merge_execution_evidence(
        first_merge,
        [item],
    )

    assert second_merge == first_merge
    assert len(second_merge) == 1


def test_merge_refreshes_mutable_fields_and_preserves_first_seen():
    existing = _commit(
        sha="abc123",
        title="Initial commit title",
        first_seen_at="2026-07-13T00:01:00Z",
        last_seen_at="2026-07-13T00:01:00Z",
    )

    incoming = _commit(
        sha="abc123",
        title="Corrected commit title",
        first_seen_at="2026-07-13T00:03:00Z",
        last_seen_at="2026-07-13T00:04:00Z",
    )

    merged = merge_execution_evidence(
        [existing],
        [incoming],
    )

    assert len(merged) == 1
    assert merged[0].title == "Corrected commit title"
    assert merged[0].first_seen_at == _timestamp(
        "2026-07-13T00:01:00Z"
    )
    assert merged[0].last_seen_at == _timestamp(
        "2026-07-13T00:04:00Z"
    )


def test_merge_keeps_distinct_external_identities():
    first = _commit(
        sha="abc123",
        title="First commit",
        first_seen_at="2026-07-13T00:01:00Z",
        last_seen_at="2026-07-13T00:01:00Z",
    )
    second = _commit(
        sha="def456",
        title="Second commit",
        first_seen_at="2026-07-13T00:02:00Z",
        last_seen_at="2026-07-13T00:02:00Z",
    )

    merged = merge_execution_evidence(
        [first],
        [second],
    )

    assert len(merged) == 2
    assert {
        item.external_id
        for item in merged
    } == {"abc123", "def456"}
