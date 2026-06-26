import re
from typing import Any, List


ANCHOR_RULES = [
    (
        "retrieval augmented generation",
        ["retrieval augmented generation", "rag"],
    ),
    (
        "question answering",
        ["question answering", "question-answering", "qa system"],
    ),
    (
        "kubernetes",
        ["kubernetes", "k8s"],
    ),
    (
        "autoscaling",
        ["autoscaling", "auto scaling", "auto-scaling"],
    ),
]


def normalize_text(text: Any) -> str:
    return " ".join(
        re.findall(r"[a-z0-9]+", str(text or "").lower())
    )


def extract_required_anchor_terms(query: str) -> List[str]:
    normalized_query = normalize_text(query)
    anchors = []

    for anchor, aliases in ANCHOR_RULES:
        normalized_aliases = [
            normalize_text(alias)
            for alias in aliases
        ]

        if any(alias in normalized_query for alias in normalized_aliases):
            anchors.append(anchor)

    return anchors
