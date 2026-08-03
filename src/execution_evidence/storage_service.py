from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

from execution_evidence.sqlite_store import (
    DEFAULT_WORKSPACE_ID,
    SQLiteRepositoryEvidenceStore,
)
from execution_evidence.sqlite_execution_event_store import (
    SQLiteExecutionEventStore,
)
from execution_evidence.store import (
    RepositoryEvidenceStore,
)
from execution_evidence.storage_readiness import (
    ExecutionEvidenceStorageReadiness,
    assess_sqlite_database_readiness,
)
from planning.roadmap_registry import (
    SQLiteRoadmapSnapshotRegistry,
)


RoadmapRegistryRuntimeStatus = Literal[
    "ready",
    "unavailable_legacy_store",
    "unavailable_error",
]


@dataclass(frozen=True)
class ExecutionEvidenceStorageRuntime:
    evidence_store: RepositoryEvidenceStore
    trusted_sqlite_service: Optional[
        "TrustedSQLiteStorageService"
    ]
    roadmap_registry: Optional[
        SQLiteRoadmapSnapshotRegistry
    ]
    roadmap_registry_status: (
        RoadmapRegistryRuntimeStatus
    )
    remediation: Optional[str] = None


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

        trusted_storage_usable = (
            readiness.status == "ready"
            or (
                readiness.status == "degraded"
                and readiness.checks.get(
                    "trusted_receipt_compatible",
                    False,
                )
            )
        )

        if not trusted_storage_usable:
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

    def build_execution_event_store(
        self,
    ) -> SQLiteExecutionEventStore:
        return self.build_execution_event_store_for_workspace(
            self._workspace_id
        )

    def build_execution_event_store_for_workspace(
        self,
        workspace_id: str,
    ) -> SQLiteExecutionEventStore:
        if not isinstance(workspace_id, str):
            raise ValueError(
                "Execution event store workspace ID "
                "must be text."
            )

        if not workspace_id:
            raise ValueError(
                "Execution event store workspace ID "
                "must be non-empty."
            )

        if workspace_id != workspace_id.strip():
            raise ValueError(
                "Execution event store workspace ID "
                "must not contain surrounding whitespace."
            )

        return SQLiteExecutionEventStore(
            self._path,
            workspace_id=workspace_id,
            initialize_schema=False,
        )
