from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
)

from research_retrieval_service import retrieve_ranked_evidence
from evidence_domain_inference import infer_domain_from_evidence
from github_corpus_search import search_github_project_corpus
from project_corpus_search import search_project_corpus

if TYPE_CHECKING:
    from query_semantics import QuerySemanticSnapshot


def add_source_type(
    items: List[Dict],
    source_type: str,
    retrieval_phase: str,
) -> List[Dict]:
    enriched_items = []

    for item in items:
        enriched_item = dict(item)
        enriched_item["source_type"] = enriched_item.get(
            "source_type",
            source_type,
        )
        enriched_item["retrieval_phase"] = retrieval_phase
        enriched_items.append(enriched_item)

    return enriched_items


def deduplicate_evidence(items: List[Dict]) -> List[Dict]:
    seen = set()
    unique_items = []

    for item in items:
        source_type = str(item.get("source_type", "unknown"))
        url = str(item.get("url", "")).strip()
        title = str(item.get("title", "")).strip().lower()

        identity = (
            source_type,
            url or title,
        )

        if identity in seen:
            continue

        seen.add(identity)
        unique_items.append(item)

    return unique_items


def interleave_evidence_groups(
    groups: List[List[Dict]],
) -> List[Dict]:
    merged = []

    max_length = max(
        (len(group) for group in groups),
        default=0,
    )

    for index in range(max_length):
        for group in groups:
            if index < len(group):
                merged.append(group[index])

    return merged


def merge_evidence_groups(
    focused_research: List[Dict],
    focused_projects: List[Dict],
    focused_github: List[Dict],
    broad_research: List[Dict],
    broad_projects: List[Dict],
    broad_github: List[Dict],
    top_k: int,
) -> List[Dict]:
    """
    Focused evidence is always prioritized.

    Broad evidence remains available as a fallback when the focused pass
    cannot provide enough unique evidence items.
    """
    focused_items = interleave_evidence_groups(
        [
            focused_projects,
            focused_research,
            focused_github,
        ]
    )

    broad_items = interleave_evidence_groups(
        [
            broad_projects,
            broad_research,
            broad_github,
        ]
    )

    return deduplicate_evidence(
        focused_items + broad_items
    )[:top_k]


def build_focused_query(
    original_query: str,
    inferred_focus: str,
) -> str:
    focus_phrase = inferred_focus.replace("_", " ").strip()

    if not focus_phrase or inferred_focus == "general":
        return original_query

    return f"{original_query} {focus_phrase}"


USER_DIRECTION_ALIASES = {
    "ai / ml": "ai_ml",
    "ai/ml": "ai_ml",
    "ai_ml": "ai_ml",
    "full-stack / software engineering": "software_engineering",
    "full stack / software engineering": "software_engineering",
    "full-stack": "software_engineering",
    "software engineering": "software_engineering",
    "cloud / platform": "cloud_platform",
    "cloud/platform": "cloud_platform",
    "cloud_platform": "cloud_platform",
    "cybersecurity": "cybersecurity",
    "fintech": "fintech",
    "blockchain": "blockchain",
    "education technology": "education_tech",
    "education_tech": "education_tech",
}


def normalize_selected_direction(
    selected_direction: Optional[str],
) -> Optional[str]:
    if not selected_direction:
        return None

    normalized = selected_direction.strip().lower()

    return USER_DIRECTION_ALIASES.get(
        normalized,
        normalized.replace(" ", "_").replace("/", "_"),
    )


def retrieve_evidence(
    user_query: str,
    top_k: int = 6,
    intent_hints: Optional[List[str]] = None,
    selected_direction: Optional[str] = None,
    semantic_snapshot: Optional[
        "QuerySemanticSnapshot"
    ] = None,
) -> Dict:
    """
    Two-pass evidence retrieval.

    Pass 1:
    Broad retrieval across research, project patterns, and GitHub references
    using the corrected user query without domain-derived expansion.

    Pass 2:
    Evidence-based family/focus inference, followed by focused retrieval.
    """
    # Broad retrieval must remain independent of domain inference.
    # Keep this compatibility field equal to the actual broad query.
    expanded_query = user_query

    broad_top_k = max(top_k, 6)
    focused_top_k = max(top_k, 6)

    broad_research = add_source_type(
        retrieve_ranked_evidence(
            query=expanded_query,
            top_k=broad_top_k,
            strategy="hybrid_rrf",
        ),
        source_type="research_paper",
        retrieval_phase="broad",
    )

    broad_projects = add_source_type(
        search_project_corpus(
            expanded_query,
            top_k=broad_top_k,
            domain_filter=None,
        ),
        source_type="project_pattern",
        retrieval_phase="broad",
    )

    broad_github = add_source_type(
        search_github_project_corpus(
            expanded_query,
            top_k=broad_top_k,
            domain_filter=None,
        ),
        source_type="github_repository",
        retrieval_phase="broad",
    )

    broad_evidence = (
        broad_research
        + broad_projects
        + broad_github
    )

    inference = infer_domain_from_evidence(
        broad_evidence,
        intent_hints=intent_hints,
    )

    confirmed_direction = normalize_selected_direction(
        selected_direction,
    )

    if confirmed_direction:
        inference = {
            **inference,
            "inferred_domain_family": confirmed_direction,
            "family_confidence": 1.0,
            "inferred_focus": confirmed_direction,
            "focus_confidence": 1.0,
            "requires_clarification": False,
            "selection_source": "user_confirmed",
        }

    inferred_focus = inference.get(
        "inferred_focus",
        "general",
    )

    focused_query = build_focused_query(
        original_query=user_query,
        inferred_focus=inferred_focus,
    )

    focused_research = add_source_type(
        retrieve_ranked_evidence(
            query=focused_query,
            top_k=focused_top_k,
            strategy="hybrid_rrf",
        ),
        source_type="research_paper",
        retrieval_phase="focused",
    )

    focused_projects = add_source_type(
        search_project_corpus(
            focused_query,
            top_k=focused_top_k,
            domain_filter=inferred_focus,
        ),
        source_type="project_pattern",
        retrieval_phase="focused",
    )

    focused_github = add_source_type(
        search_github_project_corpus(
            focused_query,
            top_k=focused_top_k,
            domain_filter=inferred_focus,
        ),
        source_type="github_repository",
        retrieval_phase="focused",
    )

    merged_results = merge_evidence_groups(
        focused_research=focused_research,
        focused_projects=focused_projects,
        focused_github=focused_github,
        broad_research=broad_research,
        broad_projects=broad_projects,
        broad_github=broad_github,
        top_k=top_k,
    )

    return {
        "query": user_query,
        "expanded_query": expanded_query,
        "focused_query": focused_query,
        "detected_intent": "unknown",
        "selected_route": "broad_then_focused",
        "selected_direction": normalize_selected_direction(
            selected_direction,
        ),
        "inference": inference,
        "research_results": focused_research,
        "project_results": focused_projects,
        "github_results": focused_github,
        "broad_research_results": broad_research,
        "broad_project_results": broad_projects,
        "broad_github_results": broad_github,
        "merged_results": merged_results,
    }