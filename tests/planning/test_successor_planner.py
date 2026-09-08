import pytest

from planning.candidate_models import CandidateDirection
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_relevance import EmbeddingVector
from planning.successor_planner import build_successor_plan


def evidence_items():
    return [
        {
            "source_id": "paper-1",
            "source_type": "research_paper",
            "title": "Platform Incident Investigation",
            "excerpt": (
                "Event correlation supports incident investigation "
                "and operational diagnosis."
            ),
            "support_scope": "direct",
        }
    ]


def candidate(title, workflow):
    return {
        "title": title,
        "problem_statement": (
            "Platform engineers need a clearer investigation workflow."
        ),
        "target_user": "Platform engineers",
        "core_workflow": workflow,
        "mvp_scope": [
            "Load representative operational records.",
            workflow[0],
            "Show evidence-backed investigation findings.",
        ],
        "success_metrics": [
            "Reduce time required to investigate failures."
        ],
        "evidence_relationship": (
            "Uses retained evidence about incident investigation."
        ),
        "source_ids": ["paper-1"],
        "assumptions": ["Use representative synthetic records."],
        "suggested_stack": ["Python", "FastAPI"],
    }


def complete_response():
    return {
        "candidates": [
            candidate(
                "Incident Timeline Investigator",
                [
                    "Build an incident timeline.",
                    "Trace correlated operational events.",
                ],
            ),
            candidate(
                "Service Dependency Explorer",
                [
                    "Map affected service dependencies.",
                    "Trace downstream operational impact.",
                ],
            ),
            candidate(
                "Failure Pattern Analyzer",
                [
                    "Group recurring failure signals.",
                    "Compare recurring incident patterns.",
                ],
            ),
        ]
    }


class RaisingProvider:
    def generate(self, prompt):
        raise RuntimeError("provider unavailable")


def build(provider):
    from planning.evidence_support import (
        CandidateEvidenceSupportScorer,
    )

    class BuildEncoder:
        def encode_text(self, text):
            from planning.semantic_goal_relevance import EmbeddingVector

            if "Platform Incident Investigation" in text:
                return EmbeddingVector((0.5, 0.5, 0.5))

            return EmbeddingVector((1.0, 0.0, 0.0))

    return build_successor_plan(
        evidence_items=evidence_items(),
        user_goal="Build a platform incident investigation project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
            "preferred_stack": ["Python", "FastAPI"],
        },
        detected_domain=None,
        provider=provider,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            BuildEncoder()
        ),
        semantic_diversity_scorer=None,
    )


def test_provider_failure_returns_explicit_non_ready_result():
    result = build(RaisingProvider())

    assert result.status == "provider_error"
    assert result.candidates == []
    assert result.ready is False
    assert result.diagnostics["reason_code"] == "provider_error"


def test_malformed_provider_output_returns_explicit_non_ready_result():
    result = build(
        MockCandidateGenerationProvider(
            response={"unexpected": []}
        )
    )

    assert result.status == "provider_invalid_output"
    assert result.candidates == []
    assert result.ready is False
    assert result.diagnostics["reason_code"] == (
        "provider_invalid_output"
    )


def test_zero_valid_candidates_returns_no_valid_candidates():
    response = complete_response()

    for item in response["candidates"]:
        item["source_ids"] = ["invented-source"]

    result = build(
        MockCandidateGenerationProvider(response=response)
    )

    assert result.status == "no_valid_candidates"
    assert result.candidates == []
    assert result.ready is False
    assert result.diagnostics["generated_candidate_count"] == 3
    assert result.diagnostics["valid_candidate_count"] == 0


def test_incomplete_selected_set_is_not_promotable():
    response = complete_response()
    response["candidates"] = response["candidates"][:2]

    result = build(
        MockCandidateGenerationProvider(response=response)
    )

    assert result.status == "insufficient_candidates"
    assert result.candidates == []
    assert result.ready is False
    assert result.diagnostics["selected_candidate_count"] == 2
    assert result.diagnostics["required_candidate_count"] == 3


def test_result_contract_keeps_candidates_at_planning_layer():
    response = complete_response()

    result = build(
        MockCandidateGenerationProvider(response=response)
    )

    if result.candidates:
        assert all(
            isinstance(item, CandidateDirection)
            for item in result.candidates
        )

    assert not hasattr(result, "ideas")

class ControlledEncoder:
    def encode_text(self, text):
        if "Incident Timeline Investigator" in text:
            return EmbeddingVector((1.0, 0.0, 0.0))

        if "Service Dependency Explorer" in text:
            return EmbeddingVector((0.0, 1.0, 0.0))

        if "Failure Pattern Analyzer" in text:
            return EmbeddingVector((0.0, 0.0, 1.0))

        if "Platform Incident Investigation" in text:
            return EmbeddingVector((0.5, 0.5, 0.5))

        raise AssertionError(f"Unexpected text: {text}")


def test_ready_result_requires_shared_candidate_set_gate():
    encoder = ControlledEncoder()
    response = complete_response()

    result = build_successor_plan(
        evidence_items=evidence_items(),
        user_goal="Build a platform incident investigation project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
            "preferred_stack": ["Python", "FastAPI"],
        },
        detected_domain=None,
        provider=MockCandidateGenerationProvider(response=response),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "ready"
    assert result.ready is True
    assert result.assessment is not None
    assert result.assessment["status"] == "ready"

    assert len(result.candidates) == 3
    assert all(
        isinstance(item, CandidateDirection)
        for item in result.candidates
    )

    expected_titles = {
        item["title"]
        for item in response["candidates"]
    }
    actual_titles = {
        item.title
        for item in result.candidates
    }

    assert actual_titles == expected_titles
    assert result.diagnostics["reason_code"] == "ready"
    assert result.diagnostics["required_candidate_count"] == 3
    assert result.diagnostics["gate_status"] == "ready"


def test_missing_diversity_fails_closed_as_needs_review():
    encoder = ControlledEncoder()

    result = build_successor_plan(
        evidence_items=evidence_items(),
        user_goal="Build a platform incident investigation project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
        },
        detected_domain=None,
        provider=MockCandidateGenerationProvider(
            response=complete_response()
        ),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=None,
    )

    assert result.status == "needs_review"
    assert result.ready is False
    assert result.candidates == []

    assert result.assessment is not None
    assert result.assessment["status"] == "needs_review"
    assert (
        result.assessment["signals"][
            "semantic_diversity_assessed"
        ]
        is False
    )

    assert result.diagnostics["reason_code"] == "needs_review"
    assert result.diagnostics["gate_status"] == "needs_review"


class PlannerBugProvider:
    def generate(self, prompt):
        return complete_response()


def test_internal_planner_runtime_error_is_not_mislabeled_provider_error(
    monkeypatch,
):
    def raise_planner_bug(*args, **kwargs):
        raise RuntimeError("internal ranking bug")

    monkeypatch.setattr(
        "planning.planning_orchestrator.rank_candidates",
        raise_planner_bug,
    )

    encoder = ControlledEncoder()

    with pytest.raises(RuntimeError, match="internal ranking bug"):
        build_successor_plan(
            evidence_items=evidence_items(),
            user_goal=(
                "Build a platform incident investigation project."
            ),
            constraints={
                "time_available": "3 weeks",
                "target_roles": ["Platform Engineer"],
            },
            detected_domain=None,
            provider=PlannerBugProvider(),
            evidence_support_scorer=CandidateEvidenceSupportScorer(
                encoder
            ),
            semantic_diversity_scorer=(
                SemanticCandidateDiversityScorer(encoder)
            ),
        )


class DuplicateBridgeEncoder:
    def encode_text(self, text):
        if "Incident Timeline Investigator" in text:
            return EmbeddingVector((1.0, 0.0))

        if "Service Dependency Explorer" in text:
            return EmbeddingVector((0.98, 0.02))

        if "Failure Pattern Analyzer" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Platform Incident Investigation" in text:
            return EmbeddingVector((0.7, 0.7))

        raise AssertionError(f"Unexpected text: {text}")


def test_duplicate_complete_set_fails_closed_as_needs_repair():
    encoder = DuplicateBridgeEncoder()

    result = build_successor_plan(
        evidence_items=evidence_items(),
        user_goal="Build a platform incident investigation project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
        },
        detected_domain=None,
        provider=MockCandidateGenerationProvider(
            response=complete_response()
        ),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "needs_repair"
    assert result.ready is False
    assert result.candidates == []

    assert result.assessment is not None
    assert result.assessment["status"] == "needs_repair"
    assert (
        result.assessment["signals"]["semantic_diversity_passed"]
        is False
    )

    assert result.diagnostics["reason_code"] == "needs_repair"
    assert result.diagnostics["gate_status"] == "needs_repair"


def test_hard_gate_failure_blocks_and_withholds_candidates(
    monkeypatch,
):
    import planning.candidate_set_gate as gate

    original = gate.assess_promotion_eligibility

    def with_blocker(*args, **kwargs):
        assessment = original(*args, **kwargs)

        if (
            kwargs["candidate"].title
            != "Incident Timeline Investigator"
        ):
            return assessment

        return type(assessment)(
            candidate_title=assessment.candidate_title,
            status="ineligible",
            eligible_for_product_promotion=False,
            blocking_reasons=[
                "Candidate does not cite directly retained evidence."
            ],
            review_reasons=[],
            signals=dict(assessment.signals),
        )

    monkeypatch.setattr(
        gate,
        "assess_promotion_eligibility",
        with_blocker,
    )

    encoder = ControlledEncoder()

    result = build_successor_plan(
        evidence_items=evidence_items(),
        user_goal="Build a platform incident investigation project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
        },
        detected_domain=None,
        provider=MockCandidateGenerationProvider(
            response=complete_response()
        ),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "blocked"
    assert result.ready is False
    assert result.candidates == []

    assert result.assessment is not None
    assert result.assessment["status"] == "blocked"
    assert (
        result.assessment["signals"]["eligible_candidate_count"]
        == 2
    )

    assert result.diagnostics["reason_code"] == "blocked"
    assert result.diagnostics["gate_status"] == "blocked"
