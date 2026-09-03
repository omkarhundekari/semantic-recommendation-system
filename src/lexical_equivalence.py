from __future__ import annotations

import re
from typing import Any, Dict, Tuple


def normalize_lexical_form(value: Any) -> str:
    """
    Normalize a surface form for lexical-identity lookup only.

    This module deliberately contains no domain, family, focus,
    routing, evidence, or authority semantics.
    """
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            str(value or "").lower(),
        )
    )


_EQUIVALENCE_GROUPS: Tuple[Tuple[str, ...], ...] = (
    (
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "rag",
    ),
)


_EQUIVALENCE_INDEX: Dict[str, Tuple[str, ...]] = {}

for group in _EQUIVALENCE_GROUPS:
    normalized_group = tuple(
        dict.fromkeys(
            normalize_lexical_form(value)
            for value in group
            if normalize_lexical_form(value)
        )
    )

    for value in normalized_group:
        _EQUIVALENCE_INDEX[value] = normalized_group


def get_lexically_equivalent_forms(
    value: Any,
) -> Tuple[str, ...]:
    """
    Return strict surface-form equivalents for one lexical concept.

    Unknown/open-world terms remain valid and simply map to
    themselves. Equivalence never assigns semantic authority.
    """
    normalized = normalize_lexical_form(value)

    if not normalized:
        return tuple()

    return _EQUIVALENCE_INDEX.get(
        normalized,
        (normalized,),
    )
