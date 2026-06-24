from typing import Any, Dict, List, Mapping, Sequence


def build_blind_candidates(
    query_entry: Mapping[str, Any],
) -> List[Dict[str, str]]:
    """
    Build the candidate view shown to a human relevance labeler.

    Deliberately excludes retrieval method, rank, score, and provenance.
    """
    candidates: List[Dict[str, str]] = []

    for candidate in query_entry.get("candidate_pool", []):
        candidates.append(
            {
                "document_id": str(candidate["document_id"]),
                "title": str(candidate.get("title", "Untitled Paper")),
                "abstract": str(candidate.get("abstract", "")),
                "category": str(
                    candidate.get("category", "Unknown Category")
                ),
                "published": str(candidate.get("published", "")),
                "source": str(candidate.get("source", "")),
            }
        )

    return candidates


def build_label_record(
    document_id: str,
    relevance: int,
) -> Dict[str, Any]:
    """
    Build one durable relevance-label record.

    Relevance scale:
    2 = highly relevant
    1 = partially relevant
    0 = irrelevant
    """
    if relevance not in {0, 1, 2}:
        raise ValueError("Relevance must be 0, 1, or 2.")

    normalized_document_id = str(document_id).strip()

    if not normalized_document_id:
        raise ValueError("document_id is required.")

    return {
        "document_id": normalized_document_id,
        "relevance": relevance,
    }
