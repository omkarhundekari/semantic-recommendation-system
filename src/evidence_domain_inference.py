from collections import defaultdict
from typing import Dict, List, Optional

from domain_taxonomy import (
    get_domain_family,
    get_focus_from_category,
    normalize_value,
)


INTENT_ALIGNMENT_BOOST = 1.0

KNOWN_FAMILIES = {
    "ai_ml",
    "software_engineering",
    "cloud_platform",
    "cybersecurity",
    "blockchain",
    "fintech",
    "education_tech",
}

SOURCE_WEIGHTS = {
    "research_paper": 1.00,
    "project_pattern": 1.05,
    "github_repository": 1.05,
}


def get_item_focus(item: Dict) -> str:
    """
    Resolves the most specific known focus from an evidence item.

    Research papers can use arXiv categories such as cs.CR.
    Project and GitHub corpora normally use direct categories such as
    cybersecurity, frontend, cloud, or ai_ml.
    """
    category = item.get("category", "")
    category_focus = get_focus_from_category(category)

    if category_focus and category_focus != "general":
        return category_focus

    normalized_category = normalize_value(category)

    if get_domain_family(normalized_category) != "general":
        return normalized_category

    return "general"


def get_rank_weight(rank: int) -> float:
    """
    Higher-ranked results carry more influence while avoiding a
    single top result dominating the decision.
    """
    return 1.0 / (rank + 1)


def get_source_weight(source_type: str) -> float:
    return SOURCE_WEIGHTS.get(source_type, 1.0)


def get_hint_families(intent_hints: Optional[List[str]]) -> List[str]:
    """
    Supports both direct focus hints such as cybersecurity and broad family
    hints such as software_engineering or cloud_platform.
    """
    families = []

    for hint in intent_hints or []:
        normalized_hint = normalize_value(hint)

        if normalized_hint in KNOWN_FAMILIES:
            family = normalized_hint
        else:
            family = get_domain_family(normalized_hint)

        if family != "general" and family not in families:
            families.append(family)

    return families


def get_hint_focuses(intent_hints: Optional[List[str]]) -> List[str]:
    focuses = []

    for hint in intent_hints or []:
        normalized_hint = normalize_value(hint)

        if normalized_hint in KNOWN_FAMILIES:
            continue

        if (
            normalized_hint != "general"
            and get_domain_family(normalized_hint) != "general"
            and normalized_hint not in focuses
        ):
            focuses.append(normalized_hint)

    return focuses


def build_candidate_families(
    family_scores: Dict[str, float],
    family_sources: Dict[str, set],
) -> List[Dict]:
    total_score = sum(family_scores.values())

    candidates = []

    for family, score in family_scores.items():
        share = score / total_score if total_score else 0.0

        candidates.append(
            {
                "family": family,
                "score": round(score, 4),
                "share": round(share, 4),
                "supporting_sources": sorted(family_sources[family]),
                "source_count": len(family_sources[family]),
            }
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["source_count"],
        ),
        reverse=True,
    )


def build_candidate_focuses(
    focus_scores: Dict[str, float],
    focus_sources: Dict[str, set],
) -> List[Dict]:
    total_score = sum(focus_scores.values())

    candidates = []

    for focus, score in focus_scores.items():
        share = score / total_score if total_score else 0.0

        candidates.append(
            {
                "focus": focus,
                "family": get_domain_family(focus),
                "score": round(score, 4),
                "share": round(share, 4),
                "supporting_sources": sorted(focus_sources[focus]),
                "source_count": len(focus_sources[focus]),
            }
        )

    return sorted(
        candidates,
        key=lambda candidate: (
            candidate["score"],
            candidate["source_count"],
        ),
        reverse=True,
    )


def calculate_confidence(
    score_share: float,
    source_count: int,
) -> float:
    """
    Confidence combines ranking dominance with source diversity.
    """
    source_diversity = min(source_count / 3, 1.0)

    confidence = (
        0.75 * score_share
        + 0.25 * source_diversity
    )

    return round(min(confidence, 1.0), 4)


def get_non_intent_sources(
    sources: set,
) -> set:
    return {
        source
        for source in sources
        if source != "user_intent"
    }


def infer_domain_from_evidence(
    evidence_items: List[Dict],
    intent_hints: Optional[List[str]] = None,
) -> Dict:
    """
    Infers a technical family and focus from broad retrieval evidence.

    Important rule:
    Explicit user direction can guide the final decision only when
    independently supported by at least two evidence source types.
    """
    if not evidence_items:
        return {
            "inferred_domain_family": "general",
            "family_confidence": 0.0,
            "inferred_focus": "general",
            "focus_confidence": 0.0,
            "candidate_families": [],
            "candidate_focuses": [],
            "reasoning_summary": (
                "No usable evidence was available to infer a technical direction."
            ),
            "matched_evidence": [],
            "requires_clarification": True,
        }

    family_source_support = defaultdict(dict)
    focus_source_support = defaultdict(dict)
    family_sources = defaultdict(set)
    focus_sources = defaultdict(set)
    matched_evidence = []

    for rank, item in enumerate(evidence_items):
        focus = get_item_focus(item)

        if focus == "general":
            continue

        family = get_domain_family(focus)

        if family == "general":
            continue

        source_type = str(
            item.get("source_type", "unknown")
        ).strip() or "unknown"

        support = (
            get_rank_weight(rank)
            * get_source_weight(source_type)
        )

        previous_family_support = family_source_support[family].get(
            source_type,
            0.0,
        )
        family_source_support[family][source_type] = max(
            previous_family_support,
            support,
        )

        previous_focus_support = focus_source_support[focus].get(
            source_type,
            0.0,
        )
        focus_source_support[focus][source_type] = max(
            previous_focus_support,
            support,
        )

        family_sources[family].add(source_type)
        focus_sources[focus].add(source_type)

        matched_item = dict(item)
        matched_item["inferred_family"] = family
        matched_item["inferred_focus"] = focus
        matched_item["support_score"] = round(support, 4)
        matched_evidence.append(matched_item)

    family_scores = {
        family: sum(source_support.values())
        for family, source_support in family_source_support.items()
    }

    focus_scores = {
        focus: sum(source_support.values())
        for focus, source_support in focus_source_support.items()
    }

    hint_families = get_hint_families(intent_hints)
    hint_focuses = get_hint_focuses(intent_hints)

    supported_intent_families = set()

    for family in hint_families:
        evidence_sources = get_non_intent_sources(
            family_sources.get(family, set())
        )

        if len(evidence_sources) >= 2:
            family_scores[family] = (
                family_scores.get(family, 0.0)
                + INTENT_ALIGNMENT_BOOST
            )
            family_sources[family].add("user_intent")
            supported_intent_families.add(family)

    for focus in hint_focuses:
        evidence_sources = get_non_intent_sources(
            focus_sources.get(focus, set())
        )

        if len(evidence_sources) >= 2:
            focus_scores[focus] = (
                focus_scores.get(focus, 0.0)
                + INTENT_ALIGNMENT_BOOST
            )
            focus_sources[focus].add("user_intent")

    if not family_scores:
        return {
            "inferred_domain_family": "general",
            "family_confidence": 0.0,
            "inferred_focus": "general",
            "focus_confidence": 0.0,
            "candidate_families": [],
            "candidate_focuses": [],
            "reasoning_summary": (
                "Retrieved evidence did not map confidently to a supported "
                "technical family."
            ),
            "matched_evidence": [],
            "requires_clarification": True,
        }

    candidate_families = build_candidate_families(
        family_scores=family_scores,
        family_sources=family_sources,
    )

    candidate_focuses = build_candidate_focuses(
        focus_scores=focus_scores,
        focus_sources=focus_sources,
    )

    top_family_candidate = candidate_families[0]
    top_family = top_family_candidate["family"]

    family_focus_candidates = [
        candidate
        for candidate in candidate_focuses
        if candidate["family"] == top_family
    ]

    top_focus_candidate = (
        family_focus_candidates[0]
        if family_focus_candidates
        else candidate_focuses[0]
    )

    top_focus = top_focus_candidate["focus"]

    family_confidence = calculate_confidence(
        score_share=top_family_candidate["share"],
        source_count=top_family_candidate["source_count"],
    )

    focus_confidence = calculate_confidence(
        score_share=top_focus_candidate["share"],
        source_count=top_focus_candidate["source_count"],
    )

    second_family_score = (
        candidate_families[1]["score"]
        if len(candidate_families) > 1
        else 0.0
    )

    ambiguous_evidence = (
        second_family_score > 0
        and second_family_score
        >= top_family_candidate["score"] * 0.85
    )

    explicit_intent_is_supported = (
        top_family in supported_intent_families
    )

    supported_explicit_focuses = [
        focus
        for focus in hint_focuses
        if (
            get_domain_family(focus) == top_family
            and bool(
                get_non_intent_sources(
                    focus_sources.get(focus, set())
                )
            )
        )
    ]

    explicit_focus_is_supported = bool(supported_explicit_focuses)

    if supported_explicit_focuses:
        top_focus = supported_explicit_focuses[0]
        matching_focus_candidates = [
            candidate
            for candidate in candidate_focuses
            if candidate["focus"] == top_focus
        ]

        if matching_focus_candidates:
            top_focus_candidate = matching_focus_candidates[0]
            focus_confidence = calculate_confidence(
                score_share=top_focus_candidate["share"],
                source_count=top_focus_candidate["source_count"],
            )

    explicit_focus_resolves_evidence_gap = (
        explicit_focus_is_supported
        and top_family_candidate["source_count"] >= 2
    )

    requires_clarification = (
        (
            family_confidence < 0.58
            and not explicit_focus_resolves_evidence_gap
        )
        or (
            ambiguous_evidence
            and not explicit_intent_is_supported
            and not explicit_focus_is_supported
        )
    )

    source_labels = ", ".join(
        top_family_candidate["supporting_sources"]
    )

    reasoning_summary = (
        f"Inferred {top_family} with focus on {top_focus} from "
        f"{top_family_candidate['source_count']} supporting evidence "
        f"source type(s): {source_labels}."
    )

    if explicit_intent_is_supported:
        reasoning_summary += (
            " The selected family also matches the user's explicit direction "
            "and is independently supported by multiple evidence sources."
        )

    return {
        "inferred_domain_family": top_family,
        "family_confidence": family_confidence,
        "inferred_focus": top_focus,
        "focus_confidence": focus_confidence,
        "candidate_families": candidate_families,
        "candidate_focuses": candidate_focuses,
        "reasoning_summary": reasoning_summary,
        "matched_evidence": matched_evidence[:12],
        "requires_clarification": requires_clarification,
    }