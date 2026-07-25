from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from execution_evidence.execution_event_store import (
    StoredExecutionEvent,
)


@dataclass(frozen=True)
class ProjectExecutionEventRecordSnapshot:
    project_id: str
    records: Tuple[StoredExecutionEvent, ...]
    project_watermark_sequence: int

    def __post_init__(self) -> None:
        if not self.project_id:
            raise ValueError(
                "Execution event snapshot project ID "
                "must not be empty."
            )

        if self.project_watermark_sequence < 0:
            raise ValueError(
                "Execution event snapshot watermark "
                "must not be negative."
            )

        record_sequences = tuple(
            record.store_sequence
            for record in self.records
        )

        if record_sequences != tuple(
            sorted(record_sequences)
        ):
            raise ValueError(
                "Execution event snapshot records must "
                "be ordered by ascending storage sequence."
            )

        if len(set(record_sequences)) != len(
            record_sequences
        ):
            raise ValueError(
                "Execution event snapshot storage "
                "sequences must be unique."
            )

        if not record_sequences:
            return

        highest_record_sequence = max(
            record_sequences
        )

        if (
            highest_record_sequence
            > self.project_watermark_sequence
        ):
            raise ValueError(
                "Execution event snapshot records cannot "
                "extend beyond the project watermark."
            )
