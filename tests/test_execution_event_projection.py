from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from execution_evidence.execution_event import (
    ExecutionEvent,
)
from execution_evidence.execution_event_projection import (
    ExecutionEventProjectionDuplicateEventError,
    ExecutionEventProjectionDuplicateSequenceError,
    ExecutionEventProjectionForwardReferenceError,
    ExecutionEventProjectionInvalidSequenceError,
    ExecutionEventProjectionMissingPredecessorError,
    ExecutionEventProjectionProjectMismatchError,
    build_execution_event_lineage_projection,
)
from execution_evidence.execution_event_store import (
    StoredExecutionEvent,
)


BASE_TIME = datetime(
    2026,
    7,
    22,
    12,
    0,
    tzinfo=timezone.utc,
)


def _event_id(number: int) -> str:
    return (
        "evt_00000000-0000-4000-8000-"
        f"{number:012x}"
    )


def _record(
    number: int,
    *,
    sequence: int,
    project_id: str = "project-test",
    supersedes: int | None = None,
    occurred_offset: int | None = None,
) -> StoredExecutionEvent:
    event_id = _event_id(number)

    event = ExecutionEvent(
        execution_event_id=event_id,
        supersedes_execution_event_id=(
            _event_id(supersedes)
            if supersedes is not None
            else None
        ),
        project_id=project_id,
        event_type="test.execution.event",
        occurred_at=(
            BASE_TIME
            + timedelta(
                minutes=(
                    occurred_offset
                    if occurred_offset is not None
                    else number
                )
            )
        ),
        recorded_at=(
            BASE_TIME
            + timedelta(minutes=sequence)
        ),
        source_provider="test",
        client_idempotency_key=(
            f"client-{number}"
        ),
        ingestion_method="system",
        payload={
            "number": number,
        },
    )

    return StoredExecutionEvent(
        store_sequence=sequence,
        event=event,
    )


def test_empty_projection_is_valid():
    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [],
        )
    )

    assert projection.ordered_records == ()
    assert projection.authoritative_events == ()
    assert projection.terminal_events == ()
    assert projection.conflicts == ()
    assert projection.has_conflicts is False


def test_linear_lineage_resolves_terminal_event():
    first = _record(
        1,
        sequence=1,
    )
    second = _record(
        2,
        sequence=2,
        supersedes=1,
    )
    third = _record(
        3,
        sequence=3,
        supersedes=2,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                third,
                first,
                second,
            ],
        )
    )

    assert [
        record.store_sequence
        for record in projection.ordered_records
    ] == [1, 2, 3]

    assert [
        event.execution_event_id
        for event
        in projection.authoritative_events
    ] == [
        first.event.execution_event_id,
        second.event.execution_event_id,
        third.event.execution_event_id,
    ]

    assert projection.terminal_event_ids == (
        third.event.execution_event_id,
    )
    assert projection.conflicts == ()


def test_competing_successors_surface_conflict():
    original = _record(
        1,
        sequence=1,
    )
    first_correction = _record(
        2,
        sequence=2,
        supersedes=1,
    )
    later_correction = _record(
        3,
        sequence=3,
        supersedes=1,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                later_correction,
                original,
                first_correction,
            ],
        )
    )

    assert projection.has_conflicts is True
    assert len(projection.conflicts) == 1

    conflict = projection.conflicts[0]

    assert conflict.predecessor_event_id == (
        original.event.execution_event_id
    )
    assert conflict.successor_event_ids == (
        first_correction.event.execution_event_id,
        later_correction.event.execution_event_id,
    )
    assert (
        conflict.authoritative_successor_event_id
        == later_correction.event.execution_event_id
    )

    assert projection.terminal_event_ids == (
        later_correction.event.execution_event_id,
    )
    assert (
        first_correction.event.execution_event_id
        in projection.non_authoritative_event_ids
    )


def test_authoritative_branch_continues_to_latest_tip():
    original = _record(
        1,
        sequence=1,
    )
    abandoned_correction = _record(
        2,
        sequence=2,
        supersedes=1,
    )
    authoritative_correction = _record(
        3,
        sequence=3,
        supersedes=1,
    )
    authoritative_tip = _record(
        4,
        sequence=4,
        supersedes=3,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                authoritative_tip,
                abandoned_correction,
                original,
                authoritative_correction,
            ],
        )
    )

    assert projection.terminal_event_ids == (
        authoritative_tip.event.execution_event_id,
    )

    assert (
        abandoned_correction.event.execution_event_id
        in projection.non_authoritative_event_ids
    )

    assert (
        authoritative_tip.event.execution_event_id
        in projection.authoritative_event_ids
    )


def test_independent_roots_produce_independent_terminals():
    first_root = _record(
        1,
        sequence=1,
    )
    second_root = _record(
        2,
        sequence=2,
    )
    first_tip = _record(
        3,
        sequence=3,
        supersedes=1,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                first_tip,
                second_root,
                first_root,
            ],
        )
    )

    assert projection.terminal_event_ids == (
        second_root.event.execution_event_id,
        first_tip.event.execution_event_id,
    )


def test_storage_order_controls_resolution_not_occurred_at():
    original = _record(
        1,
        sequence=1,
        occurred_offset=100,
    )
    first_correction = _record(
        2,
        sequence=2,
        supersedes=1,
        occurred_offset=500,
    )
    later_stored_correction = _record(
        3,
        sequence=3,
        supersedes=1,
        occurred_offset=-500,
    )

    projection = (
        build_execution_event_lineage_projection(
            "project-test",
            [
                first_correction,
                later_stored_correction,
                original,
            ],
        )
    )

    assert projection.terminal_event_ids == (
        later_stored_correction
        .event.execution_event_id,
    )


def test_projection_rejects_project_mismatch():
    with pytest.raises(
        ExecutionEventProjectionProjectMismatchError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                _record(
                    1,
                    sequence=1,
                    project_id="project-other",
                ),
            ],
        )


def test_projection_rejects_duplicate_event_id():
    first = _record(
        1,
        sequence=1,
    )
    duplicate = StoredExecutionEvent(
        store_sequence=2,
        event=first.event,
    )

    with pytest.raises(
        ExecutionEventProjectionDuplicateEventError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                first,
                duplicate,
            ],
        )


def test_projection_rejects_duplicate_sequence():
    with pytest.raises(
        ExecutionEventProjectionDuplicateSequenceError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                _record(
                    1,
                    sequence=1,
                ),
                _record(
                    2,
                    sequence=1,
                ),
            ],
        )


@pytest.mark.parametrize(
    "sequence",
    [0, -1],
)
def test_projection_rejects_nonpositive_sequence(
    sequence: int,
):
    with pytest.raises(
        ExecutionEventProjectionInvalidSequenceError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                _record(
                    1,
                    sequence=sequence,
                ),
            ],
        )


def test_projection_rejects_missing_predecessor():
    with pytest.raises(
        ExecutionEventProjectionMissingPredecessorError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                _record(
                    2,
                    sequence=2,
                    supersedes=1,
                ),
            ],
        )


def test_projection_rejects_forward_reference():
    predecessor = _record(
        1,
        sequence=2,
    )
    successor = _record(
        2,
        sequence=1,
        supersedes=1,
    )

    with pytest.raises(
        ExecutionEventProjectionForwardReferenceError
    ):
        build_execution_event_lineage_projection(
            "project-test",
            [
                predecessor,
                successor,
            ],
        )


def test_projection_rejects_empty_project_id():
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        build_execution_event_lineage_projection(
            "",
            [],
        )
