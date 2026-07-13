from datetime import datetime
import json
from pathlib import Path

import pytest

from execution_evidence.github_repository import (
    parse_github_repository_url,
)
from execution_evidence.models import (
    EvidenceAttribution,
    ExecutionEvidenceItem,
    RepositorySyncState,
)
from execution_evidence.snapshot import (
    GitHubRepositorySyncSnapshot,
)
from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.store import (
    InMemoryRepositoryEvidenceStore,
    StoredRepositoryEvidence,
)
from execution_evidence.store_migration import (
    RepositoryEvidenceMigrationError,
    build_repository_evidence_root_hash,
    canonical_repository_evidence_payload,
    dry_run_repository_evidence_migration,
    hash_repository_evidence,
    remove_sqlite_database_artifacts,
    verify_repository_evidence_migration,
)


SAVED_AT = datetime.fromisoformat(
    "2026-07-13T12:34:56.123456+00:00"
)

FIRST_REFERENCE = parse_github_repository_url(
    "https://github.com/owner/first"
)
SECOND_REFERENCE = parse_github_repository_url(
    "https://github.com/owner/second"
)


def _record(
    *,
    reference=FIRST_REFERENCE,
    revision: int = 0,
    with_attribution: bool = True,
) -> StoredRepositoryEvidence:
    evidence = [
        ExecutionEvidenceItem(
            repository_full_name=(
                reference.full_name
            ),
            evidence_type="commit",
            external_id="second",
            title="Second item",
            url=(
                f"{reference.canonical_url}/"
                "commit/second"
            ),
            occurred_at=SAVED_AT,
            metadata={
                "unicode": "Solvyn Δ",
            },
            first_seen_at=SAVED_AT,
            last_seen_at=SAVED_AT,
        ),
        ExecutionEvidenceItem(
            repository_full_name=(
                reference.full_name
            ),
            evidence_type="commit",
            external_id="first",
            title="First item",
            url=(
                f"{reference.canonical_url}/"
                "commit/first"
            ),
            occurred_at=SAVED_AT,
            first_seen_at=SAVED_AT,
            last_seen_at=SAVED_AT,
        ),
    ]

    attributions = []

    if with_attribution:
        attributions = [
            EvidenceAttribution(
                evidence_key=(
                    evidence[1].evidence_key
                ),
                roadmap_node_id="stage-two",
                source="manual",
                confidence=1.0,
                rationale="Accepted manually.",
                status="accepted",
                decided_at=SAVED_AT,
            ),
            EvidenceAttribution(
                evidence_key=(
                    evidence[0].evidence_key
                ),
                roadmap_node_id="stage-one",
                source="deterministic",
                confidence=0.82,
                rationale="Matched title.",
                status="suggested",
                decided_at=None,
            ),
        ]

    return StoredRepositoryEvidence(
        repository=reference,
        evidence=evidence,
        attributions=attributions,
        sync_state=RepositorySyncState(
            repository_key=(
                reference.repository_key
            ),
            status="succeeded",
            latest_commit_sha="second",
            last_attempted_at=SAVED_AT,
            last_succeeded_at=SAVED_AT,
        ),
        sync_snapshot=GitHubRepositorySyncSnapshot(
            repository_key=(
                reference.repository_key
            ),
        ),
        revision=revision,
        saved_at=SAVED_AT,
    )


def test_canonical_hash_is_deterministic():
    record = _record(revision=7)

    assert (
        canonical_repository_evidence_payload(
            record
        )
        == canonical_repository_evidence_payload(
            record.model_copy(deep=True)
        )
    )
    assert hash_repository_evidence(
        record
    ) == hash_repository_evidence(
        record.model_copy(deep=True)
    )


def test_root_hash_is_independent_of_repository_iteration_order():
    first = _record(revision=0)
    second = _record(
        reference=SECOND_REFERENCE,
        revision=9,
        with_attribution=False,
    )

    assert (
        build_repository_evidence_root_hash(
            [first, second]
        )
        == build_repository_evidence_root_hash(
            [second, first]
        )
    )


def test_dry_run_verifies_multiple_repositories_and_cleans_up(
    tmp_path: Path,
):
    source = InMemoryRepositoryEvidenceStore()
    source.restore(
        [
            _record(revision=0),
            _record(
                reference=SECOND_REFERENCE,
                revision=9,
                with_attribution=False,
            ),
        ]
    )

    report = (
        dry_run_repository_evidence_migration(
            source=source,
            destination_directory=tmp_path,
        )
    )

    assert report.verified is True
    assert report.dry_run is True
    assert report.repository_count == 2
    assert report.evidence_count == 4
    assert report.attribution_count == 2
    assert report.integrity_check == "ok"
    assert (
        report.foreign_key_violation_count
        == 0
    )
    assert report.relational_counts == {
        "repositories": 2,
        "evidence_items": 4,
        "evidence_attributions": 2,
        "repository_sync_states": 2,
        "repository_sync_snapshots": 2,
    }
    assert [
        item.revision
        for item in report.records
    ] == [
        0,
        9,
    ]
    assert not list(
        tmp_path.glob(
            "*.migrating.db*"
        )
    )


def test_dry_run_supports_empty_source(
    tmp_path: Path,
):
    report = (
        dry_run_repository_evidence_migration(
            source=(
                InMemoryRepositoryEvidenceStore()
            ),
            destination_directory=tmp_path,
        )
    )

    assert report.repository_count == 0
    assert report.evidence_count == 0
    assert report.attribution_count == 0
    assert report.verified is True
    assert not list(
        tmp_path.glob(
            "*.migrating.db*"
        )
    )


def test_verifier_detects_destination_aggregate_mismatch(
    tmp_path: Path,
):
    source_record = _record(revision=4)
    destination = (
        SQLiteRepositoryEvidenceStore(
            tmp_path / "solvyn.db"
        )
    )

    changed = source_record.model_copy(
        update={
            "revision": 5,
        },
        deep=True,
    )
    destination.restore([changed])

    with pytest.raises(
        RepositoryEvidenceMigrationError,
        match="does not match",
    ):
        verify_repository_evidence_migration(
            source_records=[source_record],
            destination=destination,
        )


def test_verifier_detects_repository_key_mismatch(
    tmp_path: Path,
):
    source_record = _record()
    destination = (
        SQLiteRepositoryEvidenceStore(
            tmp_path / "solvyn.db"
        )
    )
    destination.restore(
        [
            _record(
                reference=SECOND_REFERENCE,
                with_attribution=False,
            )
        ]
    )

    with pytest.raises(
        RepositoryEvidenceMigrationError,
        match="repository keys",
    ):
        verify_repository_evidence_migration(
            source_records=[source_record],
            destination=destination,
        )


def test_cleanup_removes_all_sqlite_artifacts(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    for suffix in (
        "",
        "-wal",
        "-shm",
        "-journal",
    ):
        Path(
            f"{database_path}{suffix}"
        ).write_text(
            "temporary",
            encoding="utf-8",
        )

    remove_sqlite_database_artifacts(
        database_path
    )

    for suffix in (
        "",
        "-wal",
        "-shm",
        "-journal",
    ):
        assert not Path(
            f"{database_path}{suffix}"
        ).exists()


def test_receipt_round_trip(
    tmp_path: Path,
):
    from execution_evidence.store_migration import (
        build_migration_receipt,
        persist_migration_receipt,
        verify_migration_receipt,
    )

    source = InMemoryRepositoryEvidenceStore()
    source.restore([_record(revision=7)])

    report = (
        dry_run_repository_evidence_migration(
            source=source,
            destination_directory=tmp_path,
        )
    ).model_copy(
        update={"source_type": "json"},
        deep=True,
    )

    database_path = tmp_path / "receipt.db"
    SQLiteRepositoryEvidenceStore(
        database_path
    )

    receipt = build_migration_receipt(
        report=report,
        source_identifier="repositories.json",
        created_at=(
            "2026-07-13T12:00:00+00:00"
        ),
    )

    persist_migration_receipt(
        database_path=database_path,
        receipt=receipt,
    )
    verify_migration_receipt(
        database_path=database_path,
        receipt=receipt,
    )


def test_destination_preflight_rejects_stale_sidecar(
    tmp_path: Path,
):
    from execution_evidence.store_migration import (
        assert_destination_artifacts_absent,
    )

    database_path = tmp_path / "solvyn.db"
    Path(
        f"{database_path}-wal"
    ).write_text(
        "stale",
        encoding="utf-8",
    )

    with pytest.raises(
        RepositoryEvidenceMigrationError,
        match="already exist",
    ):
        assert_destination_artifacts_absent(
            database_path
        )


def test_migration_lock_rejects_second_holder(
    tmp_path: Path,
):
    from execution_evidence.store_migration import (
        RepositoryEvidenceMigrationLock,
    )

    lock_path = tmp_path / "migration.lock"

    with RepositoryEvidenceMigrationLock(
        lock_path
    ):
        with pytest.raises(
            RepositoryEvidenceMigrationError,
            match="appears to be running",
        ):
            with RepositoryEvidenceMigrationLock(
                lock_path
            ):
                pass

    assert not lock_path.exists()


def test_json_dry_run_writes_report_without_destination(
    tmp_path: Path,
):
    from execution_evidence.json_store import (
        JsonRepositoryEvidenceStore,
    )
    from execution_evidence.store_migration import (
        dry_run_json_to_sqlite_migration,
    )

    source_path = tmp_path / "repositories.json"
    destination_path = tmp_path / "solvyn.db"
    report_path = tmp_path / "migration-report.json"

    JsonRepositoryEvidenceStore(
        source_path
    ).restore(
        [
            _record(revision=0),
            _record(
                reference=SECOND_REFERENCE,
                revision=9,
                with_attribution=False,
            ),
        ]
    )

    report = dry_run_json_to_sqlite_migration(
        source_path=source_path,
        destination_path=destination_path,
        report_path=report_path,
        created_at=(
            "2026-07-13T12:00:00+00:00"
        ),
    )

    assert report.verified is True
    assert report.source_type == "json"
    assert report_path.exists()
    assert not destination_path.exists()
    assert not Path(
        f"{destination_path}-wal"
    ).exists()
    assert not Path(
        f"{destination_path}-shm"
    ).exists()
    assert not destination_path.with_name(
        f".{destination_path.name}.migration.lock"
    ).exists()

    stored_report = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert stored_report == report.model_dump(
        mode="json"
    )
