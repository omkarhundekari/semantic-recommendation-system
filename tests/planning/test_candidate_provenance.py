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


def test_provenance_preserves_structured_rejection_history():
    from planning.candidate_provenance import (
        RegenerationAttemptRecord,
        RegenerationRejectionReason,
    )

    provenance = CandidateProvenance(
        planning_source="openai_repaired",
        prompt_version="v1",
        generation_attempt=3,
        rejected_alternatives=2,
        regeneration_attempts=[
            RegenerationAttemptRecord(
                attempt_number=1,
                rejection_reason=(
                    RegenerationRejectionReason.DIVERSITY_FAILURE
                ),
                candidate_title=(
                    "Schema Drift Watchtower for Data Contracts and Alerting"
                ),
                diversity_similarity_score=0.905,
            ),
            RegenerationAttemptRecord(
                attempt_number=2,
                rejection_reason=(
                    RegenerationRejectionReason.DIVERSITY_FAILURE
                ),
                candidate_title=(
                    "Data Contract Drift Reporter for Pipeline Consumers"
                ),
                diversity_similarity_score=0.8769,
            ),
        ],
        grounding_adequacy="cited_with_direct_scope",
        diversity_check_passed=True,
        promotion_eligible=True,
    )

    payload = provenance.to_dict()

    assert payload["planning_source"] == "openai_repaired"
    assert payload["rejected_alternatives"] == 2
    assert len(payload["regeneration_attempts"]) == 2
    assert payload["regeneration_attempts"][0][
        "rejection_reason"
    ] == "diversity_failure"


def test_provenance_rejects_inconsistent_rejection_history():
    from planning.candidate_provenance import (
        RegenerationAttemptRecord,
        RegenerationRejectionReason,
    )

    provenance = CandidateProvenance(
        planning_source="openai_repaired",
        generation_attempt=2,
        rejected_alternatives=0,
        regeneration_attempts=[
            RegenerationAttemptRecord(
                attempt_number=1,
                rejection_reason=(
                    RegenerationRejectionReason.GROUNDING_FAILURE
                ),
            )
        ],
    )

    import pytest

    with pytest.raises(ValueError, match="must match"):
        provenance.to_dict()


def test_provenance_rejects_attempt_at_or_after_accepted_attempt():
    from planning.candidate_provenance import (
        RegenerationAttemptRecord,
        RegenerationRejectionReason,
    )

    provenance = CandidateProvenance(
        planning_source="openai_repaired",
        generation_attempt=2,
        rejected_alternatives=1,
        regeneration_attempts=[
            RegenerationAttemptRecord(
                attempt_number=2,
                rejection_reason=(
                    RegenerationRejectionReason.PROMOTION_FAILURE
                ),
            )
        ],
    )

    import pytest

    with pytest.raises(ValueError, match="must occur before"):
        provenance.to_dict()


def test_planning_source_enum_keeps_stable_wire_values():
    from planning.candidate_provenance import PlanningSource

    assert PlanningSource.OPENAI_REPAIRED == "openai_repaired"
    assert PlanningSource.OPENAI_FALLBACK == "openai_fallback"
