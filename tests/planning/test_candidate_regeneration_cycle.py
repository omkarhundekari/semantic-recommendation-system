from planning.candidate_models import CandidateDirection, CandidateGenerationRequest
from planning.candidate_regeneration_cycle import run_mock_regeneration_cycle
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def encode_text(self, text):
        if "Pipeline Monitor" in text:
            return EmbeddingVector((1.0, 0.0))

        if "Schema Drift Contract Guard" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Data Quality Research" in text:
            return EmbeddingVector((0.0, 1.0))

        raise AssertionError(f"Unexpected text: {text}")


def make_brief():
    return EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt=(
                    "Data validation and schema checks improve "
                    "pipeline reliability."
                ),
                support_scope="direct",
            )
        ],
    )


def make_request():
    return CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )


def make_retained_candidate():
    return CandidateDirection(
        title="Pipeline Monitor",
        problem_statement=(
            "Data engineers need basic pipeline-quality monitoring."
        ),
        target_user="Data engineers",
        core_workflow=[
            "Run validation checks.",
            "Show quality alerts.",
        ],
        mvp_scope=[
            "Load pipeline records.",
            "Run validation checks.",
            "Show alert results.",
        ],
        success_metrics=["Number of quality issues detected."],
        evidence_relationship="Uses retained data-quality evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def make_directive():
    return DiversificationRepairDirective(
        replace_candidate_title="Pipeline Failure Triage",
        retain_candidate_titles=["Pipeline Monitor"],
        highest_pair_similarity=0.7915,
        reason="Candidate overlaps with a higher-ranked direction.",
        regeneration_brief={
            "preserve_user_goal": True,
            "preserve_evidence_constraints": True,
            "must_differ_from_titles": ["Pipeline Monitor"],
            "avoid_retained_workflow": [
                "Run validation checks.",
                "Show quality alerts.",
            ],
            "avoid_retained_mvp_scope": [
                "Load pipeline records.",
                "Run validation checks.",
                "Show alert results.",
            ],
            "requirement": (
                "Use a materially distinct technical workflow."
            ),
        },
    )


def make_mock_response():
    return {
        "candidate": {
            "title": "Schema Drift Contract Guard",
            "problem_statement": (
                "Data engineers need early visibility into schema drift."
            ),
            "target_user": "Data engineers",
            "core_workflow": [
                "Compare schemas against a versioned contract.",
                "Show changed fields and affected pipelines.",
            ],
            "mvp_scope": [
                "Load representative schema snapshots.",
                "Compare schemas against a versioned contract.",
                "Show detected drift findings.",
            ],
            "success_metrics": [
                "Number of schema-drift issues detected.",
            ],
            "evidence_relationship": (
                "Uses retained data-quality evidence for validation design."
            ),
            "source_ids": ["paper-1"],
            "assumptions": [
                "The MVP uses versioned sample schemas.",
            ],
            "suggested_stack": ["Python", "FastAPI"],
        }
    }


def test_runs_complete_mock_regeneration_cycle():
    encoder = ControlledEncoder()

    cycle = run_mock_regeneration_cycle(
        raw_response=make_mock_response(),
        brief=make_brief(),
        request=make_request(),
        directive=make_directive(),
        retained_candidates=[make_retained_candidate()],
        evidence_support_scorer=CandidateEvidenceSupportScorer(encoder),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert cycle.intake.is_valid is True
    assert cycle.accepted is True
    assert cycle.replacement_evaluation.replacement_status == "accepted"
    assert "Generate exactly one replacement" in cycle.prompt

    artifact = cycle.to_dict()

    assert artifact["accepted"] is True
    assert artifact["intake"]["candidate"]["title"] == (
        "Schema Drift Contract Guard"
    )
    assert artifact["replacement_evaluation"][
        "promotion_eligibility"
    ]["status"] == "eligible"
