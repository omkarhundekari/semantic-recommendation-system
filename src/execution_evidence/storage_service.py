from __future__ import annotations

from pathlib import Path

from execution_evidence.sqlite_store import (
    DEFAULT_WORKSPACE_ID,
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.storage_readiness import (
    ExecutionEvidenceStorageReadiness,
    assess_sqlite_database_readiness,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
)


class TrustedSQLiteStorageServiceError(
    RuntimeError
):
    pass


class TrustedSQLiteStorageService:
    def __init__(
        self,
        path: Path | str,
        *,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
    ) -> None:
        resolved_path = Path(path)
        resolved_workspace_id = workspace_id.strip()

        if not resolved_workspace_id:
            raise ValueError(
                "Trusted SQLite storage workspace "
                "ID must be non-empty."
            )

        readiness = (
            assess_sqlite_database_readiness(
                resolved_path
            )
        )

        if readiness.status != "ready":
            details = "; ".join(
                readiness.errors
            )

            raise TrustedSQLiteStorageServiceError(
                "Trusted SQLite storage failed "
                "readiness validation"
                + (
                    f": {details}"
                    if details
                    else "."
                )
            )

        self._path = resolved_path
        self._workspace_id = (
            resolved_workspace_id
        )
        self._readiness = readiness

    @property
    def path(self) -> Path:
        return self._path

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def readiness(
        self,
    ) -> ExecutionEvidenceStorageReadiness:
        return self._readiness.model_copy(
            deep=True
        )

    def build_repository_evidence_store(
        self,
    ) -> SQLiteRepositoryEvidenceStore:
        return SQLiteRepositoryEvidenceStore(
            self._path,
            workspace_id=self._workspace_id,
            initialize_schema=False,
        )

    def build_roadmap_snapshot_registry(
        self,
    ) -> SQLiteRoadmapSnapshotRegistry:
        return SQLiteRoadmapSnapshotRegistry(
            self._path,
            workspace_id=self._workspace_id,
            initialize_schema=False,
        )
