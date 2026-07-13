from __future__ import annotations

from typing import Iterable, List

from execution_evidence.models import ExecutionEvidenceItem


def merge_execution_evidence(
    existing: Iterable[ExecutionEvidenceItem],
    incoming: Iterable[ExecutionEvidenceItem],
) -> List[ExecutionEvidenceItem]:
    merged = {
        item.evidence_key: item
        for item in existing
    }

    for incoming_item in incoming:
        current = merged.get(incoming_item.evidence_key)

        if current is None:
            merged[incoming_item.evidence_key] = incoming_item
            continue

        merged[incoming_item.evidence_key] = incoming_item.model_copy(
            update={
                "first_seen_at": min(
                    current.first_seen_at,
                    incoming_item.first_seen_at,
                ),
                "last_seen_at": max(
                    current.last_seen_at,
                    incoming_item.last_seen_at,
                ),
            }
        )

    return sorted(
        merged.values(),
        key=lambda item: (
            item.occurred_at,
            item.evidence_key,
        ),
        reverse=True,
    )
