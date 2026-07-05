from planning.candidate_provenance import CandidateProvenance
from schemas.product_models import (
    ProjectDirection,
    VerificationResult,
)


def make_provenance():
    return CandidateProvenance(
        planning_source="openai_repaired",
        prompt_version="v1",
        generation_attempt=3,
        replacement_angle=(
            "Build a lineage-aware blast-radius explorer instead of "
            "another schema-drift workflow."
        ),
        rejected_alternatives=2,
        grounding_adequacy="cited_with_direct_scope",
        diversity_check_passed=True,
        promotion_eligible=True,
    )


def test_provenance_serializes_without_empty_optional_fields():
    payload = make_provenance().to_dict()

    assert payload["planning_source"] == "openai_repaired"
    assert payload["generation_attempt"] == 3
    assert payload["rejected_alternatives"] == 2
    assert payload["promotion_eligible"] is True
    assert "unused_optional_field" not in payload


def test_product_direction_accepts_optional_planner_provenance():
    direction = ProjectDirection(
        id="direction-1",
        title="Lineage-Aware Blast Radius Explorer",
        summary="Maps incident impact across downstream assets.",
        scope="Focused MVP",
        estimated_effort="2 weeks",
        portfolio_tier="Medium",
        difficulty="Medium",
        career_signal="Backend and data-platform engineering.",
        why_it_fits="Directly grounded in retained evidence.",
        planner_provenance=make_provenance(),
        verification=VerificationResult(
            status="passed",
            score=8,
            max_score=8,
        ),
    )

    assert direction.planner_provenance is not None
    assert (
        direction.planner_provenance.planning_source
        == "openai_repaired"
    )
