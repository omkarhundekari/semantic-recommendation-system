from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

from feasibility_scorer import score_project_feasibility
from plan_repair import repair_project_plan
from plan_verifier import verify_project_ideas
from portfolio_ladder import apply_portfolio_ladder


@dataclass(frozen=True)
class ProductEnrichmentResult:
    ideas: List[Dict[str, Any]]
    initial_verification_results: List[Dict[str, Any]]
    final_verification_results: List[Dict[str, Any]]
    repairs_by_index: List[List[str]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def enrich_product_ideas(
    ideas: List[Dict[str, Any]],
    constraints: Dict[str, Any],
) -> ProductEnrichmentResult:
    """
    Run the deterministic production enrichment pipeline over a complete,
    ordered candidate set.

    Ordering is intentionally preserved because portfolio ladder assignment
    creates Easy, Medium, and Hard directions by position. This function does
    not generate candidates or mutate caller-owned input dictionaries.
    """
    working_ideas = [
        deepcopy(idea)
        for idea in ideas
    ]

    for idea in working_ideas:
        idea["feasibility_analysis"] = score_project_feasibility(idea)

    initial_verification_results = verify_project_ideas(
        working_ideas,
        constraints,
    )

    repaired_ideas = []
    repairs_by_index = []

    for idea in working_ideas:
        repaired_idea, repairs, _ = repair_project_plan(
            idea,
            constraints,
        )
        repaired_ideas.append(repaired_idea)
        repairs_by_index.append(repairs)

    laddered_ideas = apply_portfolio_ladder(repaired_ideas)

    for idea in laddered_ideas:
        ladder_profile = (
            idea.get("feasibility_analysis", {})
            .get("build_profile", {})
        )

        rescored_feasibility = score_project_feasibility(idea)
        rescored_feasibility["build_profile"] = ladder_profile
        idea["feasibility_analysis"] = rescored_feasibility

    final_verification_results = verify_project_ideas(
        laddered_ideas,
        constraints,
    )

    return ProductEnrichmentResult(
        ideas=laddered_ideas,
        initial_verification_results=initial_verification_results,
        final_verification_results=final_verification_results,
        repairs_by_index=repairs_by_index,
    )
