import re
from typing import Optional


MODERN_ARXIV_PATTERN = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/)?"
    r"(?P<identifier>\d{4}\.\d{4,5})"
    r"(?:v\d+)?"
    r"(?:\.pdf)?"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)

LEGACY_ARXIV_PATTERN = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/)?"
    r"(?P<identifier>[a-z\-]+(?:\.[a-z]{2})?/\d{7})"
    r"(?:v\d+)?"
    r"(?:\.pdf)?"
    r"(?:[/?#].*)?$",
    re.IGNORECASE,
)


def normalize_arxiv_id(value: Optional[str]) -> Optional[str]:
    """
    Normalize an arXiv URL or identifier to its version-free base ID.

    Supported formats were verified against data/research_corpus.csv:
    - Modern: https://arxiv.org/abs/2009.08553v4 -> 2009.08553
    - Legacy: https://arxiv.org/abs/cs/0112017v2 -> cs/0112017
    """
    if not value:
        return None

    cleaned = str(value).strip()

    if not cleaned:
        return None

    modern_match = MODERN_ARXIV_PATTERN.search(cleaned)
    if modern_match:
        return modern_match.group("identifier")

    legacy_match = LEGACY_ARXIV_PATTERN.search(cleaned)
    if legacy_match:
        return legacy_match.group("identifier").lower()

    return None


def build_document_id(
    source: Optional[str],
    url: Optional[str],
    external_id: Optional[str] = None,
) -> str:
    """
    Build a namespaced stable document ID.

    Current corpus:
    - arXiv URLs become arxiv:<base_id>

    Future non-arXiv sources must provide an explicit stable external_id.
    """
    normalized_arxiv_id = normalize_arxiv_id(url)

    if normalized_arxiv_id:
        return f"arxiv:{normalized_arxiv_id}"

    source_key = str(source or "unknown").strip().lower()
    stable_external_id = str(external_id or "").strip()

    if stable_external_id:
        return f"{source_key}:{stable_external_id}"

    raise ValueError(
        "Cannot build a stable document ID without a recognized arXiv URL "
        "or an explicit external_id."
    )
