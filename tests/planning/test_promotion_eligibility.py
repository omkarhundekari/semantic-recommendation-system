from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.grounding_adequacy import (
    GroundingAdequacy,
    GroundingAdequacyTrace,
)
from planning.promotion_eligibility import (
    assess_promotion_eligibility,
)
from planning.semantic_candidate_diversity import (
    CandidateDiversityPair,
    CandidateDiversityTrace,
)
from planning.shadow_quality_warnings import (
    ShadowQualityWarning,
    ShadowQualityWarningAssessment,
)


def make_candidate(title="Incident Correlation Workbench"):
    return CandidateDirection(
        title=title,
        problem_statement="Connect incident and deployment signals.",
        target_user="platform engineers",
        core_workflow=[
            "Load operational records.",
            "Correlate related events.",
        ],
        mvp_scope=[
            "Load sample records.",
            "Correlate related events.",
            "Show an investigation timeline.",
        ],
        success_metrics=["Reduce investigation time."],
        evidence_relationship="Uses retained incident evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def make_validation(is_valid=True):
    return CandidateValidationResult(is_valid=is_valid)


def make_grounding(
    adequacy_class=GroundingAdequacy.CITED_WITH_DIRECT_SCOPE,
):
    return GroundingAdequacyTrace(
        candidate_title="Incident Correlation Workbench",
        adequacy_class=adequacy_class,
        cited_source_ids=["paper-1"],
        cited_source_scopes=["direct"],
        cited_alignment_scores=[0.48],
        min_cited_alignment=0.48,
        max_cited_alignment=0.48,
        direct_sources_in_brief=1,
        uncited_direct_sources=[],
        adequacy_reason="Candidate cites direct evidence.",
    )


def empty_warnings():
    return ShadowQualityWarningAssessment(
        warnings=[],
        signals={},
    )


def test_marks_structurally_grounded_candidate_as_eligible():
    assessment = assess_promotion_eligibility(
        candidate=make_candidate(),
        validation=make_validation(),
        grounding=make_grounding(),
        quality_warnings=empty_warnings(),
    )

    assert assessment.status == "eligible"
    assert assessment.eligible_for_product_promotion is True
    assert assessment.blocking_reasons == []
    assert assessment.review_reasons == []


def test_blocks_candidate_without_direct_evidence_citation():
    assessment = assess_promotion_eligibility(
        candidate=make_candidate(),
        validation=make_validation(),
        grounding=make_grounding(
            GroundingAdequacy.CITED_ONLY_ADJACENT
        ),
        quality_warnings=empty_warnings(),
    )

    assert assessment.status == "ineligible"
    assert assessment.eligible_for_product_promotion is False
    assert assessment.blocking_reasons == [
        "Candidate does not cite directly retained evidence."
    ]


def test_keeps_soft_quality_warnings_as_review_signals():
    warnings = ShadowQualityWarningAssessment(
        warnings=[
            ShadowQualityWarning(
                code="low_goal_alignment",
                message="Low alignment.",
                details={
                    "candidates": [
                        {
                            "candidate_title": (
                                "Incident Correlation Workbench"
                            ),
                            "raw_cosine": 0.41,
                        }
                    ]
                },
            )
        ],
        signals={},
    )

    assessment = assess_promotion_eligibility(
        candidate=make_candidate(),
        validation=make_validation(),
        grounding=make_grounding(),
        quality_warnings=warnings,
    )

    assert assessment.status == "needs_review"
    assert assessment.eligible_for_product_promotion is False
    assert assessment.blocking_reasons == []
    assert assessment.review_reasons == [
        "Candidate has low semantic alignment with the requested goal."
    ]


def test_blocks_candidate_in_flagged_semantic_duplicate_pair():
    diversity = CandidateDiversityTrace(
        similarity_threshold=0.82,
        pairwise_similarity=[
            CandidateDiversityPair(
                candidate_a_title="Incident Correlation Workbench",
                candidate_b_title="Incident Timeline Explorer",
                raw_cosine=0.86,
                flagged=True,
            )
        ],
        passed=False,
    )

    assessment = assess_promotion_eligibility(
        candidate=make_candidate(),
        validation=make_validation(),
        grounding=make_grounding(),
        quality_warnings=empty_warnings(),
        semantic_candidate_diversity=diversity,
    )

    assert assessment.status == "ineligible"
    assert assessment.signals["has_flagged_duplicate_pair"] is True
    assert assessment.blocking_reasons == [
        "Candidate is part of a semantically duplicate direction pair."
    ]


def test_blocks_invalid_candidate_before_promotion():
    assessment = assess_promotion_eligibility(
        candidate=make_candidate(),
        validation=make_validation(is_valid=False),
        grounding=make_grounding(),
        quality_warnings=empty_warnings(),
    )

    assert assessment.status == "ineligible"
    assert assessment.blocking_reasons == [
        "Candidate failed planner validation."
    ]
