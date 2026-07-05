from planning.candidate_feasibility_prescreen import (
    prescreen_candidate_feasibility,
)
from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.promotion_eligibility import (
    assess_promotion_eligibility,
)
from planning.candidate_models import CandidateValidationResult
from planning.grounding_adequacy import (
    GroundingAdequacy,
    GroundingAdequacyTrace,
)
from planning.shadow_quality_warnings import (
    ShadowQualityWarningAssessment,
)


def make_brief():
    return EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data validation improves pipeline reliability.",
                support_scope="direct",
            )
        ],
    )


def make_candidate(mvp_scope=None, stack=None):
    return CandidateDirection(
        title="Lineage-Aware Pipeline Impact Explorer",
        problem_statement=(
            "Data engineers need to identify downstream assets affected "
            "by a quality incident."
        ),
        target_user="data engineers",
        core_workflow=[
            "Load incident and lineage records.",
            "Trace affected downstream assets.",
        ],
        mvp_scope=mvp_scope or [
            "Load representative lineage edges.",
            "Compute affected downstream assets.",
            "Show an impact report.",
        ],
        success_metrics=["Reduce time required to assess incident impact."],
        evidence_relationship="Uses retained data-quality evidence.",
        source_ids=["paper-1"],
        suggested_stack=stack or ["Python", "FastAPI"],
    )


def make_request(time_available="3 weeks", preferred_stack=None):
    return CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        time_available=time_available,
        target_roles=["Data Engineer"],
        preferred_stack=preferred_stack or [],
    )


def test_prescreen_marks_constraint_aligned_candidate_as_feasible():
    result = prescreen_candidate_feasibility(
        candidate=make_candidate(),
        brief=make_brief(),
        request=make_request(),
        detected_domain="data_engineering",
    )

    assert result.status == "feasible"
    assert result.blocking_reasons == []
    assert result.review_reasons == []
    assert result.feasibility_analysis["complexity"] in {
        "Medium",
        "High",
    }


def test_prescreen_blocks_scope_that_exceeds_short_timeline():
    result = prescreen_candidate_feasibility(
        candidate=make_candidate(
            mvp_scope=[
                "Load lineage edges.",
                "Build a graph.",
                "Trace downstream assets.",
                "Rank severity.",
                "Add ownership mapping.",
                "Add a dashboard.",
            ]
        ),
        brief=make_brief(),
        request=make_request(time_available="weekend"),
        detected_domain="data_engineering",
    )

    assert result.status == "blocked_by_constraints"
    assert result.blocking_reasons == [
        "Candidate scope exceeds the stated timeline."
    ]


def test_prescreen_marks_preferred_stack_mismatch_for_review():
    result = prescreen_candidate_feasibility(
        candidate=make_candidate(),
        brief=make_brief(),
        request=make_request(preferred_stack=["Go"]),
        detected_domain="data_engineering",
    )

    assert result.status == "needs_review"
    assert result.review_reasons == [
        "Candidate does not reflect the preferred technology stack."
    ]


def test_promotion_blocks_candidate_with_blocked_feasibility_prescreen():
    candidate = make_candidate()
    prescreen = prescreen_candidate_feasibility(
        candidate=candidate,
        brief=make_brief(),
        request=make_request(time_available="weekend"),
        detected_domain="data_engineering",
    )

    assessment = assess_promotion_eligibility(
        candidate=candidate,
        validation=CandidateValidationResult(is_valid=True),
        grounding=GroundingAdequacyTrace(
            candidate_title=candidate.title,
            adequacy_class=GroundingAdequacy.CITED_WITH_DIRECT_SCOPE,
            cited_source_ids=["paper-1"],
            cited_source_scopes=["direct"],
            cited_alignment_scores=[0.6],
            min_cited_alignment=0.6,
            max_cited_alignment=0.6,
            direct_sources_in_brief=1,
            uncited_direct_sources=[],
            adequacy_reason="Candidate cites direct evidence.",
        ),
        quality_warnings=ShadowQualityWarningAssessment(
            warnings=[],
            signals={},
        ),
        feasibility_prescreen=prescreen,
    )

    assert assessment.status == "ineligible"
    assert assessment.eligible_for_product_promotion is False
    assert "Candidate scope exceeds the stated timeline." in (
        assessment.blocking_reasons
    )
    assert assessment.signals["feasibility_prescreen"]["status"] == (
        "blocked_by_constraints"
    )
