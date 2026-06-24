from typing import Any, Dict, Mapping


def build_research_record(
    paper: Mapping[str, Any],
    index: int,
) -> Dict[str, Any]:
    """
    Build the canonical research-paper record used across retrieval,
    evaluation, and product evidence flows.

    The corpus must provide document_id. Missing IDs are treated as a
    data-integrity error instead of silently falling back to mutable row
    positions or titles.
    """
    document_id = str(paper.get("document_id", "")).strip()

    if not document_id:
        raise ValueError(
            "Research corpus record is missing a stable document_id."
        )

    content = str(paper.get("content", "") or "")

    return {
        "document_id": document_id,
        "index": int(index),
        "title": str(
            paper.get("title", "Untitled Paper") or "Untitled Paper"
        ),
        "content": content,
        "abstract": content,
        "category": str(
            paper.get("category", "Unknown Category")
            or "Unknown Category"
        ),
        "authors": str(paper.get("authors", "") or ""),
        "published": str(paper.get("published", "") or ""),
        "url": str(paper.get("url", "") or ""),
        "source": str(paper.get("source", "") or ""),
    }
