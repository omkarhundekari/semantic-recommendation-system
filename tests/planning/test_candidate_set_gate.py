from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_set_gate import assess_candidate_set
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def encode_text(self, text):
        if "Pipeline Monitor" in text:
            return EmbeddingVector((1.0, 0.0, 0.0))

        if "Schema Drift Guard" in text:
            return EmbeddingVector((0.0, 1.0, 0.0))

        if "Lineage Explorer" in text:
            return EmbeddingVector((0.0, 0.0, 1.0))

        if "Data Quality Research" in text:
            return EmbeddingVector((0.5, 0.5, 0.5))

        raise AssertionError(f"Unexpected text: {text}")


def make_candidate(title, workflow):
    return CandidateDirection(
        title=title,
        problem_statement="Data teams need an inspectable workflow.",
        target_user="Data engineers",
        core_workflow=workflow,
        mvp_scope=[
            "Load sample records.",
            "Analyze reliability signals.",
            "Show actionable findings.",
        ],
        success_metrics=["Make reliability issues easier to diagnose."],
        evidence_relationship="Uses retained data-quality evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def test_marks_complete_grounded_diverse_set_ready():
    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain="data_engineering",
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "ready"
    assert result.signals["candidate_count"] == 3
    assert result.signals["semantic_diversity_passed"] is True
    assert result.signals["eligible_candidate_count"] == 3
    assert len(result.promotion_eligibility) == 3


class DuplicateEncoder:
    def encode_text(self, text):
        if "RAG Evaluation Dashboard" in text:
            return EmbeddingVector((1.0, 0.0))

        if "RAG Quality Console" in text:
            return EmbeddingVector((0.98, 0.02))

        if "Citation Inspector" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Data Quality Research" in text:
            return EmbeddingVector((0.7, 0.7))

        raise AssertionError(f"Unexpected text: {text}")


def test_marks_grounded_semantic_duplicate_set_as_needs_repair():
    candidates = [
        make_candidate(
            "RAG Evaluation Dashboard",
            ["Compare RAG runs.", "Inspect quality regressions."],
        ),
        make_candidate(
            "RAG Quality Console",
            ["Inspect RAG quality.", "Compare model runs."],
        ),
        make_candidate(
            "Citation Inspector",
            ["Inspect citations.", "Show unsupported claims."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = DuplicateEncoder()

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain="data_engineering",
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "needs_repair"
    assert result.signals["semantic_diversity_passed"] is False
    assert result.signals["eligible_candidate_count"] < 3


def test_marks_soft_promotion_signal_as_needs_review(monkeypatch):
    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    import planning.candidate_set_gate as gate

    original = gate.assess_promotion_eligibility

    def with_review(*args, **kwargs):
        assessment = original(*args, **kwargs)

        if kwargs["candidate"].title != "Pipeline Monitor":
            return assessment

        return type(assessment)(
            candidate_title=assessment.candidate_title,
            status="needs_review",
            eligible_for_product_promotion=False,
            blocking_reasons=[],
            review_reasons=["Manual review required."],
            signals=dict(assessment.signals),
        )

    monkeypatch.setattr(
        gate,
        "assess_promotion_eligibility",
        with_review,
    )

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain="data_engineering",
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "needs_review"
    assert result.signals["semantic_diversity_passed"] is True
    assert result.signals["eligible_candidate_count"] == 2


def test_blocks_candidate_set_with_hard_promotion_failure(monkeypatch):
    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    import planning.candidate_set_gate as gate

    original = gate.assess_promotion_eligibility

    def with_blocker(*args, **kwargs):
        assessment = original(*args, **kwargs)

        if kwargs["candidate"].title != "Pipeline Monitor":
            return assessment

        return type(assessment)(
            candidate_title=assessment.candidate_title,
            status="ineligible",
            eligible_for_product_promotion=False,
            blocking_reasons=[
                "Candidate does not cite directly retained evidence."
            ],
            blocking_reason_codes=[
                "missing_direct_evidence"
            ],
            review_reasons=[],
            signals=dict(assessment.signals),
        )

    monkeypatch.setattr(
        gate,
        "assess_promotion_eligibility",
        with_blocker,
    )

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain="data_engineering",
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "blocked"
    assert result.signals["semantic_diversity_passed"] is True
    assert result.signals["eligible_candidate_count"] == 2


def test_can_assess_set_without_inventing_feasibility_domain(
    monkeypatch,
):
    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    import planning.candidate_set_gate as gate

    def unexpected_prescreen(*args, **kwargs):
        raise AssertionError(
            "Feasibility prescreen must not run without "
            "an authoritative detected domain."
        )

    monkeypatch.setattr(
        gate,
        "prescreen_candidate_feasibility",
        unexpected_prescreen,
    )

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain=None,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "ready"
    assert result.signals["feasibility_assessed"] is False


def test_uses_precomputed_diversity_and_quality_warnings(
    monkeypatch,
):
    from planning.semantic_candidate_diversity import (
        CandidateDiversityTrace,
    )
    from planning.shadow_quality_warnings import (
        ShadowQualityWarningAssessment,
    )

    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    diversity = CandidateDiversityTrace(
        similarity_threshold=0.78,
        pairwise_similarity=[],
        passed=True,
    )
    warnings = ShadowQualityWarningAssessment(
        warnings=[],
        signals={"quality_warning_count": 0},
    )

    import planning.candidate_set_gate as gate

    def unexpected_diversity(*args, **kwargs):
        raise AssertionError(
            "Precomputed semantic diversity must not be recomputed."
        )

    def unexpected_warnings(*args, **kwargs):
        raise AssertionError(
            "Precomputed quality warnings must not be recomputed."
        )

    monkeypatch.setattr(
        gate,
        "assess_shadow_quality_warnings",
        unexpected_warnings,
    )

    class FailingDiversityScorer:
        def assess_candidates(self, *args, **kwargs):
            return unexpected_diversity()

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain=None,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=FailingDiversityScorer(),
        semantic_candidate_diversity=diversity,
        quality_warnings=warnings,
    )

    assert result.status == "ready"
    assert result.semantic_candidate_diversity == diversity.to_dict()
    assert result.quality_warnings == warnings.to_dict()


def test_assesses_candidates_without_claiming_set_ready_when_diversity_missing():
    candidates = [
        make_candidate(
            "Pipeline Monitor",
            ["Run validation checks.", "Show quality alerts."],
        ),
        make_candidate(
            "Schema Drift Guard",
            ["Compare schemas.", "Explain changed fields."],
        ),
        make_candidate(
            "Lineage Explorer",
            ["Trace dependencies.", "Show downstream impact."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = ControlledEncoder()

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain=None,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=None,
        semantic_candidate_diversity=None,
    )

    assert result.status == "needs_review"
    assert result.semantic_candidate_diversity is None
    assert result.signals["semantic_diversity_assessed"] is False
    assert result.signals["eligible_candidate_count"] == 3


def test_duplicate_with_independent_hard_blocker_stays_blocked(
    monkeypatch,
):
    candidates = [
        make_candidate(
            "RAG Evaluation Dashboard",
            ["Compare RAG runs.", "Inspect quality regressions."],
        ),
        make_candidate(
            "RAG Quality Console",
            ["Inspect RAG quality.", "Compare model runs."],
        ),
        make_candidate(
            "Citation Inspector",
            ["Inspect citations.", "Show unsupported claims."],
        ),
    ]
    brief = EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data reliability needs observability.",
                support_scope="direct",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )
    encoder = DuplicateEncoder()

    import planning.candidate_set_gate as gate

    original = gate.assess_promotion_eligibility

    def with_independent_blocker(*args, **kwargs):
        assessment = original(*args, **kwargs)

        if kwargs["candidate"].title != "RAG Evaluation Dashboard":
            return assessment

        return type(assessment)(
            candidate_title=assessment.candidate_title,
            status="ineligible",
            eligible_for_product_promotion=False,
            blocking_reasons=[
                *assessment.blocking_reasons,
                "Independent hard blocker.",
            ],
            blocking_reason_codes=[
                *assessment.blocking_reason_codes,
                "independent_hard_blocker",
            ],
            review_reasons=assessment.review_reasons,
            signals=dict(assessment.signals),
        )

    monkeypatch.setattr(
        gate,
        "assess_promotion_eligibility",
        with_independent_blocker,
    )

    result = assess_candidate_set(
        candidates=candidates,
        brief=brief,
        request=request,
        detected_domain=None,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.signals["semantic_diversity_passed"] is False
    assert result.status == "blocked"
