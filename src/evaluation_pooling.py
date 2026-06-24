from typing import Any, Dict, List, Mapping, Sequence


def build_union_pool(
    results_by_method: Mapping[str, Sequence[Mapping[str, Any]]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Build a stable, deduplicated union of top-K retrieval candidates.

    Identity is based only on document_id. Retrieval provenance is retained
    separately for reporting and must remain hidden during blind labeling.
    """
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    pooled: Dict[str, Dict[str, Any]] = {}

    for method_name, results in results_by_method.items():
        for rank, result in enumerate(results[:top_k], start=1):
            document_id = str(result.get("document_id", "")).strip()

            if not document_id:
                raise ValueError(
                    f"Result from method '{method_name}' is missing document_id."
                )

            if document_id not in pooled:
                abstract = str(
                    result.get("abstract")
                    or result.get("content")
                    or ""
                )

                pooled[document_id] = {
                    "document_id": document_id,
                    "title": str(
                        result.get("title", "Untitled Paper")
                        or "Untitled Paper"
                    ),
                    "abstract": abstract,
                    "category": str(
                        result.get("category", "Unknown Category")
                        or "Unknown Category"
                    ),
                    "published": str(result.get("published", "") or ""),
                    "url": str(result.get("url", "") or ""),
                    "source": str(result.get("source", "") or ""),
                    "provenance": [],
                }

            pooled[document_id]["provenance"].append(
                {
                    "method": method_name,
                    "rank": rank,
                }
            )

    candidates = list(pooled.values())

    for candidate in candidates:
        candidate["provenance"] = sorted(
            candidate["provenance"],
            key=lambda item: (item["method"], item["rank"]),
        )

    return sorted(
        candidates,
        key=lambda candidate: candidate["document_id"],
    )
