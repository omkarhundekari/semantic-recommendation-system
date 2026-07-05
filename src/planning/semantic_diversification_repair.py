from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Sequence, Set

from planning.shadow_quality_warnings import (
    NEAR_DUPLICATE_WARNING_THRESHOLD,
)


@dataclass(frozen=True)
class DiversificationRepairDirective:
    replace_candidate_title: str
    retain_candidate_titles: List[str]
    highest_pair_similarity: float
    reason: str
    regeneration_brief: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiversificationRepairPlan:
    status: str
    directives: List[DiversificationRepairDirective]
    signals: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "directives": [
                directive.to_dict()
                for directive in self.directives
            ],
            "signals": dict(self.signals),
        }


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _candidate_score(candidate: Dict[str, Any]) -> float:
    ranking = candidate.get("ranking", {})

    if not isinstance(ranking, dict):
        return 0.0

    return _as_float(ranking.get("score"))


def _candidate_titles(
    selected_candidates: Sequence[Dict[str, Any]],
) -> Set[str]:
    return {
        str(candidate.get("title", "")).strip()
        for candidate in selected_candidates
        if str(candidate.get("title", "")).strip()
    }


def _connected_components(
    adjacency: Dict[str, Set[str]],
) -> List[Set[str]]:
    remaining = set(adjacency)
    components = []

    while remaining:
        start = remaining.pop()
        component = {start}
        frontier = [start]

        while frontier:
            current = frontier.pop()

            for neighbor in adjacency.get(current, set()):
                if neighbor not in component:
                    component.add(neighbor)
                    remaining.discard(neighbor)
                    frontier.append(neighbor)

        components.append(component)

    return components


def build_semantic_diversification_repair_plan(
    selected_candidates: Sequence[Dict[str, Any]],
    semantic_candidate_diversity: Dict[str, Any],
    similarity_threshold: float = NEAR_DUPLICATE_WARNING_THRESHOLD,
) -> DiversificationRepairPlan:
    """
    Build a shadow-only regeneration plan for semantically close candidates.

    This does not mutate candidate order, call an LLM, or change selection.
    It identifies close clusters, keeps the highest-ranked candidate in each
    cluster, and marks the remaining directions for a future targeted retry.
    """
    candidates_by_title = {
        str(candidate.get("title", "")).strip(): candidate
        for candidate in selected_candidates
        if str(candidate.get("title", "")).strip()
    }
    valid_titles = _candidate_titles(selected_candidates)

    adjacency = {
        title: set()
        for title in valid_titles
    }
    pair_scores: Dict[frozenset, float] = {}

    for pair in semantic_candidate_diversity.get(
        "pairwise_similarity",
        [],
    ):
        if not isinstance(pair, dict):
            continue

        left = str(pair.get("candidate_a_title", "")).strip()
        right = str(pair.get("candidate_b_title", "")).strip()
        similarity = _as_float(pair.get("raw_cosine"))

        if (
            not left
            or not right
            or left == right
            or left not in valid_titles
            or right not in valid_titles
            or similarity < similarity_threshold
        ):
            continue

        adjacency[left].add(right)
        adjacency[right].add(left)
        pair_scores[frozenset({left, right})] = similarity

    close_adjacency = {
        title: neighbors
        for title, neighbors in adjacency.items()
        if neighbors
    }
    components = _connected_components(close_adjacency)

    directives = []

    for component in components:
        ranked_titles = sorted(
            component,
            key=lambda title: (
                -_candidate_score(candidates_by_title[title]),
                title.lower(),
            ),
        )
        retained_title = ranked_titles[0]

        for replace_title in ranked_titles[1:]:
            related_scores = [
                score
                for pair, score in pair_scores.items()
                if replace_title in pair
            ]
            highest_similarity = max(related_scores, default=0.0)

            retained_candidate = candidates_by_title[retained_title]
            replacement_candidate = candidates_by_title[replace_title]

            directives.append(
                DiversificationRepairDirective(
                    replace_candidate_title=replace_title,
                    retain_candidate_titles=[retained_title],
                    highest_pair_similarity=round(
                        highest_similarity,
                        4,
                    ),
                    reason=(
                        "Candidate is semantically close to a higher-ranked "
                        "direction and should be regenerated with a "
                        "materially different workflow focus."
                    ),
                    regeneration_brief={
                        "preserve_user_goal": True,
                        "preserve_evidence_constraints": True,
                        "must_differ_from_titles": [retained_title],
                        "avoid_retained_workflow": list(
                            retained_candidate.get(
                                "core_workflow",
                                [],
                            )
                        ),
                        "avoid_retained_mvp_scope": list(
                            retained_candidate.get(
                                "mvp_scope",
                                [],
                            )
                        ),
                        "replace_existing_focus": {
                            "title": replace_title,
                            "core_workflow": list(
                                replacement_candidate.get(
                                    "core_workflow",
                                    [],
                                )
                            ),
                            "mvp_scope": list(
                                replacement_candidate.get(
                                    "mvp_scope",
                                    [],
                                )
                            ),
                        },
                        "requirement": (
                            "Propose one evidence-grounded direction with "
                            "a materially distinct technical workflow, "
                            "target-user interaction, or system boundary."
                        ),
                    },
                )
            )

    return DiversificationRepairPlan(
        status=(
            "repair_planned"
            if directives
            else "no_repair_needed"
        ),
        directives=directives,
        signals={
            "candidate_count": len(valid_titles),
            "similarity_threshold": similarity_threshold,
            "close_cluster_count": len(components),
            "replacement_count": len(directives),
        },
    )
