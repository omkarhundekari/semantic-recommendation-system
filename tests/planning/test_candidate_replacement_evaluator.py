import pytest

from planning.candidate_models import (
    CandidateDirection,
    CandidateValidationResult,
)
from planning.candidate_replacement_evaluator import (
    evaluate_regenerated_candidate,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def encode_text(self, text):
        if "Pipeline Monitor" in text:
            return EmbeddingVector((1.0, 0.0))

        if "Schema Drift Contract Guard" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Pipeline Monitor Clone" in text:
            return EmbeddingVector((1.0, 0.0))

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


def make_candidate(title, workflow, mvp_scope):
    return CandidateDirection(
        title=title,
        problem_statement=(
            "Data engineers need an inspectable quality workflow."
        ),
        target_user="Data engineers",
        core_workflow=workflow,
        mvp_scope=mvp_scope,
        success_metrics=["Number of quality issues detected."],
        evidence_relationship=(
            "Uses retained data-quality evidence."
        ),
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def make_components():
    encoder = ControlledEncoder()

    return (
        CandidateEvidenceSupportScorer(encoder),
        SemanticCandidateDiversityScorer(encoder),
    )


def test_accepts_distinct_directly_grounded_replacement():
    retained = make_candidate(
        "Pipeline Monitor",
        [
            "Run validation checks.",
            "Show quality alerts.",
        ],
        [
            "Load pipeline records.",
            "Run validation checks.",
            "Show alert results.",
        ],
    )
    replacement = make_candidate(
        "Schema Drift Contract Guard",
        [
            "Compare schemas against a contract.",
            "Show changed fields and affected pipelines.",
        ],
        [
            "Load representative schema snapshots.",
            "Compare schemas against a versioned contract.",
            "Show detected drift findings.",
        ],
    )
    support_scorer, diversity_scorer = make_components()

    evaluation = evaluate_regenerated_candidate(
        candidate=replacement,
        validation=CandidateValidationResult(is_valid=True),
        retained_candidates=[retained],
        brief=make_brief(),
        evidence_support_scorer=support_scorer,
        semantic_diversity_scorer=diversity_scorer,
    )

    assert evaluation.replacement_status == "accepted"
    assert evaluation.accepted_as_diverse_replacement is True
    assert evaluation.ready_for_product_promotion is True
    assert evaluation.reasons == []
    assert evaluation.promotion_eligibility["status"] == "eligible"


def test_rejects_replacement_that_remains_semantically_close():
    retained = make_candidate(
        "Pipeline Monitor",
        [
            "Run validation checks.",
            "Show quality alerts.",
        ],
        [
            "Load pipeline records.",
            "Run validation checks.",
            "Show alert results.",
        ],
    )
    replacement = make_candidate(
        "Pipeline Monitor Clone",
        [
            "Run checks.",
            "Show more monitoring alerts.",
        ],
        [
            "Load pipeline records.",
            "Run validation checks.",
            "Show monitor alerts.",
        ],
    )
    support_scorer, diversity_scorer = make_components()

    evaluation = evaluate_regenerated_candidate(
        candidate=replacement,
        validation=CandidateValidationResult(is_valid=True),
        retained_candidates=[retained],
        brief=make_brief(),
        evidence_support_scorer=support_scorer,
        semantic_diversity_scorer=diversity_scorer,
    )

    assert evaluation.replacement_status == "rejected"
    assert evaluation.accepted_as_diverse_replacement is False
    assert evaluation.ready_for_product_promotion is False
    assert evaluation.promotion_eligibility["status"] == "ineligible"
    assert evaluation.reasons == [
        (
            "Replacement candidate remains semantically close to a "
            "retained direction."
        )
    ]


def test_requires_at_least_one_retained_candidate():
    candidate = make_candidate(
        "Schema Drift Contract Guard",
        [
            "Compare schemas.",
            "Show changed fields.",
        ],
        [
            "Load schemas.",
            "Compare contracts.",
            "Show drift findings.",
        ],
    )
    support_scorer, diversity_scorer = make_components()

    with pytest.raises(ValueError, match="retained candidate"):
        evaluate_regenerated_candidate(
            candidate=candidate,
            validation=CandidateValidationResult(is_valid=True),
            retained_candidates=[],
            brief=make_brief(),
            evidence_support_scorer=support_scorer,
            semantic_diversity_scorer=diversity_scorer,
        )
