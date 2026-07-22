from __future__ import annotations

from dataclasses import dataclass

from execution_evidence.execution_event_projection import (
    ExecutionEventLineageProjection,
    build_execution_event_lineage_projection,
)
from execution_evidence.execution_event_store import (
    ExecutionEventStore,
)


class ExecutionEventProjectionServiceError(
    RuntimeError
):
    pass


class ExecutionEventProjectionUnsupportedStoreError(
    ExecutionEventProjectionServiceError
):
    pass


@dataclass(frozen=True)
class ExecutionEventProjectionService:
    store: ExecutionEventStore
    default_limit: int = 1000

    def __post_init__(self) -> None:
        if (
            self.default_limit < 1
            or self.default_limit > 1000
        ):
            raise ValueError(
                "Execution event projection limit "
                "must be between 1 and 1000."
            )

    def project_lineage(
        self,
        project_id: str,
        *,
        limit: int | None = None,
    ) -> ExecutionEventLineageProjection:
        if not project_id:
            raise ValueError(
                "Execution event projection project "
                "ID must not be empty."
            )

        resolved_limit = (
            self.default_limit
            if limit is None
            else limit
        )

        if (
            resolved_limit < 1
            or resolved_limit > 1000
        ):
            raise ValueError(
                "Execution event projection limit "
                "must be between 1 and 1000."
            )

        try:
            records = (
                self.store
                .list_project_event_records(
                    project_id,
                    limit=resolved_limit,
                )
            )
        except NotImplementedError as error:
            raise (
                ExecutionEventProjectionUnsupportedStoreError(
                    "The configured execution event "
                    "store does not expose "
                    "authoritative storage order."
                )
            ) from error

        return (
            build_execution_event_lineage_projection(
                project_id,
                records,
            )
        )
