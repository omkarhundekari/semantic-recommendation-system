from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Dict,
    FrozenSet,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_store import (
    StoredExecutionEvent,
)


class ExecutionEventProjectionError(RuntimeError):
    pass


class ExecutionEventProjectionProjectMismatchError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionDuplicateEventError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionDuplicateSequenceError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionInvalidSequenceError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionMissingPredecessorError(
    ExecutionEventProjectionError
):
    pass


class ExecutionEventProjectionForwardReferenceError(
    ExecutionEventProjectionError
):
    pass


@dataclass(frozen=True)
class ExecutionEventLineageConflict:
    predecessor_event_id: str
    successor_event_ids: Tuple[str, ...]
    authoritative_successor_event_id: str


@dataclass(frozen=True)
class ExecutionEventLineageProjection:
    project_id: str
    ordered_records: Tuple[
        StoredExecutionEvent,
        ...,
    ]
    authoritative_event_ids: FrozenSet[str]
    terminal_event_ids: Tuple[str, ...]
    conflicts: Tuple[
        ExecutionEventLineageConflict,
        ...,
    ]

    @property
    def authoritative_events(
        self,
    ) -> Tuple[ExecutionEvent, ...]:
        return tuple(
            record.event
            for record in self.ordered_records
            if (
                record.event.execution_event_id
                in self.authoritative_event_ids
            )
        )

    @property
    def terminal_events(
        self,
    ) -> Tuple[ExecutionEvent, ...]:
        terminal_ids = set(
            self.terminal_event_ids
        )

        return tuple(
            record.event
            for record in self.ordered_records
            if (
                record.event.execution_event_id
                in terminal_ids
            )
        )

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)

    @property
    def non_authoritative_event_ids(
        self,
    ) -> FrozenSet[str]:
        return frozenset(
            record.event.execution_event_id
            for record in self.ordered_records
            if (
                record.event.execution_event_id
                not in self.authoritative_event_ids
            )
        )


def build_execution_event_lineage_projection(
    project_id: str,
    records: Iterable[StoredExecutionEvent],
) -> ExecutionEventLineageProjection:
    if not project_id:
        raise ValueError(
            "Execution event projection project ID "
            "must not be empty."
        )

    ordered_records = tuple(
        sorted(
            records,
            key=lambda record: (
                record.store_sequence
            ),
        )
    )

    if not ordered_records:
        return ExecutionEventLineageProjection(
            project_id=project_id,
            ordered_records=(),
            authoritative_event_ids=frozenset(),
            terminal_event_ids=(),
            conflicts=(),
        )

    _validate_records(
        project_id=project_id,
        ordered_records=ordered_records,
    )

    records_by_id = {
        record.event.execution_event_id: record
        for record in ordered_records
    }

    successors_by_id: Dict[
        str,
        List[StoredExecutionEvent],
    ] = {}

    roots: List[StoredExecutionEvent] = []

    for record in ordered_records:
        predecessor_id = (
            record.event
            .supersedes_execution_event_id
        )

        if predecessor_id is None:
            roots.append(record)
            continue

        successors_by_id.setdefault(
            predecessor_id,
            [],
        ).append(record)

    authoritative_successors: Dict[
        str,
        StoredExecutionEvent,
    ] = {}

    conflicts: List[
        ExecutionEventLineageConflict
    ] = []

    for (
        predecessor_id,
        successors,
    ) in successors_by_id.items():
        ordered_successors = sorted(
            successors,
            key=lambda record: (
                record.store_sequence
            ),
        )

        authoritative = ordered_successors[-1]

        authoritative_successors[
            predecessor_id
        ] = authoritative

        if len(ordered_successors) > 1:
            conflicts.append(
                ExecutionEventLineageConflict(
                    predecessor_event_id=(
                        predecessor_id
                    ),
                    successor_event_ids=tuple(
                        successor.event
                        .execution_event_id
                        for successor
                        in ordered_successors
                    ),
                    authoritative_successor_event_id=(
                        authoritative.event
                        .execution_event_id
                    ),
                )
            )

    authoritative_event_ids: Set[str] = set()
    terminal_event_ids: List[str] = []

    for root in roots:
        current = root
        visited: Set[str] = set()

        while True:
            current_id = (
                current.event.execution_event_id
            )

            if current_id in visited:
                raise ExecutionEventProjectionError(
                    "Execution event supersession "
                    "lineage contains a cycle."
                )

            visited.add(current_id)
            authoritative_event_ids.add(
                current_id
            )

            successor = (
                authoritative_successors.get(
                    current_id
                )
            )

            if successor is None:
                terminal_event_ids.append(
                    current_id
                )
                break

            current = successor

    represented_event_ids = {
        record.event.execution_event_id
        for record in ordered_records
    }

    reachable_event_ids = _collect_reachable_ids(
        roots=roots,
        successors_by_id=successors_by_id,
    )

    if reachable_event_ids != represented_event_ids:
        unreachable = sorted(
            represented_event_ids
            - reachable_event_ids
        )

        raise ExecutionEventProjectionError(
            "Execution event lineage contains "
            "unreachable events: "
            + ", ".join(unreachable)
        )

    conflicts.sort(
        key=lambda conflict: (
            records_by_id[
                conflict.predecessor_event_id
            ].store_sequence
        )
    )

    terminal_event_ids.sort(
        key=lambda event_id: (
            records_by_id[event_id]
            .store_sequence
        )
    )

    return ExecutionEventLineageProjection(
        project_id=project_id,
        ordered_records=ordered_records,
        authoritative_event_ids=frozenset(
            authoritative_event_ids
        ),
        terminal_event_ids=tuple(
            terminal_event_ids
        ),
        conflicts=tuple(conflicts),
    )


def _validate_records(
    *,
    project_id: str,
    ordered_records: Tuple[
        StoredExecutionEvent,
        ...,
    ],
) -> None:
    records_by_id: Dict[
        str,
        StoredExecutionEvent,
    ] = {}
    records_by_sequence: Dict[
        int,
        StoredExecutionEvent,
    ] = {}

    for record in ordered_records:
        if record.store_sequence < 1:
            raise (
                ExecutionEventProjectionInvalidSequenceError(
                    "Execution event storage sequence "
                    "must be positive."
                )
            )

        if (
            record.store_sequence
            in records_by_sequence
        ):
            raise (
                ExecutionEventProjectionDuplicateSequenceError(
                    "Execution event storage sequence "
                    "must be unique within a "
                    "projection."
                )
            )

        event = record.event

        if event.project_id != project_id:
            raise (
                ExecutionEventProjectionProjectMismatchError(
                    "Execution event does not belong "
                    "to the projected project."
                )
            )

        if (
            event.execution_event_id
            in records_by_id
        ):
            raise (
                ExecutionEventProjectionDuplicateEventError(
                    "Execution event ID must be "
                    "unique within a projection."
                )
            )

        records_by_sequence[
            record.store_sequence
        ] = record
        records_by_id[
            event.execution_event_id
        ] = record

    for record in ordered_records:
        predecessor_id = (
            record.event
            .supersedes_execution_event_id
        )

        if predecessor_id is None:
            continue

        predecessor = records_by_id.get(
            predecessor_id
        )

        if predecessor is None:
            raise (
                ExecutionEventProjectionMissingPredecessorError(
                    "Execution event supersession "
                    "target is missing from the "
                    "projection."
                )
            )

        if (
            predecessor.store_sequence
            >= record.store_sequence
        ):
            raise (
                ExecutionEventProjectionForwardReferenceError(
                    "Execution event supersession "
                    "must point to a lower storage "
                    "sequence."
                )
            )


def _collect_reachable_ids(
    *,
    roots: List[StoredExecutionEvent],
    successors_by_id: Dict[
        str,
        List[StoredExecutionEvent],
    ],
) -> Set[str]:
    reachable: Set[str] = set()
    pending = list(roots)

    while pending:
        record = pending.pop()
        event_id = (
            record.event.execution_event_id
        )

        if event_id in reachable:
            continue

        reachable.add(event_id)

        pending.extend(
            successors_by_id.get(
                event_id,
                [],
            )
        )

    return reachable
