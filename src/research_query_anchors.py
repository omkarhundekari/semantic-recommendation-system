import re
from typing import Any, List

from lexical_equivalence import (
    get_lexically_equivalent_forms,
)


ANCHOR_RULES = [
    (
        "retrieval augmented generation",
        list(
            get_lexically_equivalent_forms(
                "retrieval augmented generation"
            )
        ),
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
