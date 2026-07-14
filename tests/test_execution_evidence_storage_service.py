from __future__ import annotations

from pathlib import Path

import pytest

from execution_evidence.sqlite_store import (
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_service import (
    TrustedSQLiteStorageService,
    TrustedSQLiteStorageServiceError,
)
from execution_evidence.trusted_store import (
    initialize_fresh_trusted_store,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
)


CREATED_AT = "2026-07-13T12:00:00+00:00"


def test_service_requires_ready_trusted_database(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    service = TrustedSQLiteStorageService(
        database_path
    )

    assert service.path == database_path
    assert service.workspace_id == "local"
    assert service.readiness.status == "ready"


def test_service_rejects_missing_database(
    tmp_path: Path,
):
    with pytest.raises(
        TrustedSQLiteStorageServiceError,
        match="readiness validation",
    ):
        TrustedSQLiteStorageService(
            tmp_path / "missing.db"
        )


def test_service_rejects_schema_only_database(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    SQLiteRepositoryEvidenceStore(
        database_path
    )

    with pytest.raises(
        TrustedSQLiteStorageServiceError,
        match="trusted-store",
    ):
        TrustedSQLiteStorageService(
            database_path
        )


def test_service_builds_repositories_without_migrations(
    tmp_path: Path,
    monkeypatch,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    service = TrustedSQLiteStorageService(
        database_path
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "Runtime repository attempted to "
            "initialize the schema."
        )

    monkeypatch.setattr(
        "execution_evidence.sqlite_store."
        "initialize_execution_evidence_database",
        fail_if_called,
    )
    monkeypatch.setattr(
        "planning.roadmap_registry."
        "initialize_execution_evidence_database",
        fail_if_called,
    )

    evidence_store = (
        service.build_repository_evidence_store()
    )
    roadmap_registry = (
        service.build_roadmap_snapshot_registry()
    )

    assert isinstance(
        evidence_store,
        SQLiteRepositoryEvidenceStore,
    )
    assert isinstance(
        roadmap_registry,
        SQLiteRoadmapSnapshotRegistry,
    )
    assert evidence_store.path == database_path
    assert roadmap_registry.path == database_path


def test_service_applies_same_workspace_to_repositories(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    service = TrustedSQLiteStorageService(
        database_path,
        workspace_id="workspace-one",
    )

    evidence_store = (
        service.build_repository_evidence_store()
    )
    roadmap_registry = (
        service.build_roadmap_snapshot_registry()
    )

    assert (
        evidence_store.workspace_id
        == "workspace-one"
    )
    assert (
        roadmap_registry.workspace_id
        == "workspace-one"
    )


def test_service_readiness_result_is_defensively_copied(
    tmp_path: Path,
):
    database_path = tmp_path / "solvyn.db"

    initialize_fresh_trusted_store(
        database_path,
        created_at=CREATED_AT,
    )

    service = TrustedSQLiteStorageService(
        database_path
    )

    first = service.readiness
    first.errors.append("mutated")

    second = service.readiness

    assert second.errors == []
