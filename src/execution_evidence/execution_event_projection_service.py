from __future__ import annotations

from execution_evidence.execution_event_projection import (
    ExecutionEventLineageProjection,
    ExecutionEventProjectionError,
    build_execution_event_lineage_projection,
)
from execution_evidence.execution_event_record_snapshot import (
    ProjectExecutionEventRecordSnapshot,
)
from execution_evidence.execution_event_store import (
    ExecutionEventStore,
)


class ExecutionEventProjectionUnsupportedStoreError(
    RuntimeError
):
    pass


class ExecutionEventProjectionIncompleteSnapshotError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionService:
    def __init__(
        self,
        *,
        store: ExecutionEventStore,
    ) -> None:
        self._store = store

    def project_lineage(
        self,
        project_id: str,
    ) -> ExecutionEventLineageProjection:
        if not project_id:
            raise ValueError(
                "Execution event projection project ID "
                "must not be empty."
            )

        try:
            snapshot = (
                self._store
                .load_project_event_record_snapshot(
                    project_id
                )
            )
        except NotImplementedError as error:
            raise (
                ExecutionEventProjectionUnsupportedStoreError(
                    "The configured execution event store "
                    "does not expose complete authoritative "
                    "project snapshots."
                )
            ) from error

        if snapshot.project_id != project_id:
            raise (
                ExecutionEventProjectionIncompleteSnapshotError(
                    "Execution event snapshot belongs to "
                    "a different project."
                )
            )

        projection = (
            build_execution_event_lineage_projection(
                project_id,
                snapshot.records,
            )
        )

        if (
            projection.projection_through_sequence
            != snapshot.project_watermark_sequence
        ):
            raise (
                ExecutionEventProjectionIncompleteSnapshotError(
                    "Execution event lineage projection "
                    "does not cover the authoritative "
                    "project watermark."
                )
            )

        return projection
