from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional

from execution_evidence.execution_event import (
    ExecutionEvent,
    ExecutionEventAppendResult,
)

if TYPE_CHECKING:
    from execution_evidence.execution_event_record_snapshot import (
        ProjectExecutionEventRecordSnapshot,
    )



MAX_SYNCHRONOUS_LINEAGE_EVENTS = 100_000


@dataclass(frozen=True)
class StoredExecutionEvent:
    store_sequence: int
    event: ExecutionEvent


class ExecutionEventStoreError(RuntimeError):
    pass


class ExecutionEventProjectNotFoundError(
    ExecutionEventStoreError
):
    pass


class ExecutionEventProjectHistoryTooLargeError(
    ExecutionEventStoreError
):
    pass


class ExecutionEventNotFoundError(
    ExecutionEventStoreError
):
    pass


class ExecutionEventIdempotencyConflictError(
    ExecutionEventStoreError
):
    pass


class ExecutionEventSupersessionTargetNotFoundError(
    ExecutionEventStoreError
):
    """The referenced event is unavailable in this workspace."""


class ExecutionEventSupersessionScopeError(
    ExecutionEventStoreError
):
    """The referenced event belongs to another project."""


class ExecutionEventStore(ABC):
    @abstractmethod
    def append(
        self,
        event: ExecutionEvent,
    ) -> ExecutionEventAppendResult:
        raise NotImplementedError

    @abstractmethod
    def load(
        self,
        execution_event_id: str,
    ) -> Optional[ExecutionEvent]:
        raise NotImplementedError

    @abstractmethod
    def list_project_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[ExecutionEvent]:
        raise NotImplementedError


    def list_project_event_records(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> List[StoredExecutionEvent]:
        raise NotImplementedError(
            "This execution event store does not "
            "expose authoritative storage order."
        )


    def load_project_event_record_snapshot(
        self,
        project_id: str,
    ) -> "ProjectExecutionEventRecordSnapshot":
        raise NotImplementedError(
            "This execution event store does not "
            "expose complete authoritative project "
            "snapshots."
        )
