from typing import Dict, List, Mapping, Sequence


def assess_label_coverage(
    ranking: Sequence[Mapping[str, object]],
    labels: Mapping[str, int],
    top_k: int,
) -> Dict[str, object]:
    """
    Check whether a method's top-K ranking is fully covered by labels.

    Missing labels must exclude the method-query pair from metric scoring.
    They are never treated as irrelevant.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    requested = list(ranking[:top_k])

    document_ids = [
        str(item.get("document_id", "")).strip()
        for item in requested
    ]

    if any(not document_id for document_id in document_ids):
        raise ValueError("Ranking contains a result without document_id.")

    missing_document_ids = [
        document_id
        for document_id in document_ids
        if document_id not in labels
    ]

    labeled_count = len(document_ids) - len(missing_document_ids)
    total_count = len(document_ids)

    return {
        "eligible": len(missing_document_ids) == 0,
        "requested_count": total_count,
        "labeled_count": labeled_count,
        "missing_document_ids": missing_document_ids,
        "coverage": (
            labeled_count / total_count
            if total_count
            else 0.0
        ),
    }
