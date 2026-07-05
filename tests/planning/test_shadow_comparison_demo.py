from planning.shadow_comparison_demo import (
    build_shadow_comparison_artifact,
)


def test_comparison_artifact_keeps_legacy_and_v2_results_separate():
    evidence_payload = {
        "selected_route": "broad_then_focused",
        "expanded_query": "platform incident investigation",
        "focused_query": "platform incident investigation cloud_platform",
        "inference": {
            "inferred_focus": "cloud_platform",
        },
        "merged_results": [
            {
                "document_id": "paper-1",
                "source_type": "research_paper",
                "title": "Event Correlation for Incident Investigation",
                "abstract": (
                    "Event correlation supports service investigation."
                ),
                "retrieval_rank": 1,
            }
        ],
    }

    fixture_response = {
        "candidates": [
            {
                "title": "Incident Correlation Workbench",
                "problem_statement": "Signals are fragmented.",
                "target_user": "Platform engineers",
                "core_workflow": [
                    "Load events.",
                    "Correlate incident signals.",
                ],
                "mvp_scope": [
                    "Load sample records.",
                    "Correlate events.",
                    "Show a timeline.",
                ],
                "success_metrics": [
                    "Time to find related events.",
                ],
                "evidence_relationship": (
                    "Uses the retrieved correlation paper."
                ),
                "source_ids": ["paper-1"],
                "assumptions": [],
                "suggested_stack": ["Python"],
            }
        ]
    }

    artifact = build_shadow_comparison_artifact(
        evidence_payload=evidence_payload,
        user_goal="Build a platform incident project.",
        constraints={},
        fixture_response=fixture_response,
    )

    assert artifact["legacy_planner"]["direction_count"] == 3
    assert artifact["v2_shadow"]["status"] == "fixture_evaluated"
    assert artifact["v2_shadow"]["generation_metadata"] == {
        "prompt_version": "v1",
        "execution_mode": "fixture",
        "provider_name": "MockCandidateGenerationProvider",
        "model": None,
        "usage": {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        },
    }
    assert artifact["v2_shadow"]["shadow_readiness"]["status"] == (
        "needs_review"
    )
    assert artifact["v2_shadow"]["shadow_readiness"]["signals"][
        "selected_candidate_count"
    ] == 1
    assert artifact["v2_shadow"]["selected_candidates"][0]["title"] == (
        "Incident Correlation Workbench"
    )
    assert artifact["retrieval"]["merged_evidence_count"] == 1



def test_openai_cli_guard_blocks_before_retrieval(monkeypatch):
    import pytest
    from types import SimpleNamespace

    from planning import shadow_comparison_demo as demo

    monkeypatch.setenv("PLANNING_PROVIDER", "mock")
    monkeypatch.setenv("PLANNING_LLM_ENABLED", "false")

    monkeypatch.setattr(
        demo,
        "parse_args",
        lambda: SimpleNamespace(
            provider="openai",
            allow_live_llm=True,
        ),
    )

    def retrieval_must_not_run(*args, **kwargs):
        raise AssertionError("Retrieval must not run when guard blocks.")

    monkeypatch.setattr(
        demo,
        "retrieve_evidence",
        retrieval_must_not_run,
    )

    with pytest.raises(RuntimeError, match="PLANNING_PROVIDER=openai"):
        demo.main()


def test_comparison_artifact_keeps_semantic_shadow_separate():
    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [],
        },
        user_goal="Build an incident investigation project.",
        constraints={},
        semantic_goal_relevance=[
            {
                "candidate_key": "abc123",
                "candidate_title": "Incident Timeline Tool",
                "raw_cosine": 0.72,
                "normalized_score": 0.86,
                "goal_text_used": "Build an incident investigation project.",
                "candidate_text_used": (
                    "Incident Timeline Tool. Connect incident evidence."
                ),
            }
        ],
    )

    assert artifact["v2_shadow"]["semantic_goal_relevance"][0][
        "candidate_key"
    ] == "abc123"
    assert artifact["v2_shadow"]["selected_candidates"] == []


def test_semantic_shadow_helper_uses_selected_candidates_only():
    from planning.shadow_comparison_demo import (
        build_semantic_goal_relevance_shadow,
    )

    class FakeTrace:
        def to_dict(self):
            return {
                "candidate_key": "semantic-1",
                "candidate_title": "Incident Timeline Tool",
                "raw_cosine": 0.8,
                "normalized_score": 0.9,
                "goal_text_used": "Build an incident project.",
                "candidate_text_used": "Incident Timeline Tool.",
            }

    class FakeResult:
        trace = FakeTrace()

    class FakeScorer:
        def __init__(self):
            self.received_request = None
            self.received_candidates = None

        def score_candidates(self, request, candidates):
            self.received_request = request
            self.received_candidates = candidates
            return [FakeResult()]

    scorer = FakeScorer()
    selected_candidates = [
        {
            "title": "Incident Timeline Tool",
            "problem_statement": "Connect operational signals.",
            "target_user": "Platform engineers",
            "core_workflow": [
                "Load incident data.",
                "Show a shared timeline.",
            ],
            "mvp_scope": [
                "Load sample records.",
                "Order records by time.",
                "Render the timeline.",
            ],
            "success_metrics": ["Faster incident review."],
            "evidence_relationship": "Uses retained evidence.",
            "source_ids": ["paper-1"],
            "assumptions": [],
            "suggested_stack": ["Python"],
            "ranking": {"score": 0.9},
        }
    ]

    result = build_semantic_goal_relevance_shadow(
        selected_candidates=selected_candidates,
        generation_request=object(),
        scorer=scorer,
    )

    assert result[0]["candidate_key"] == "semantic-1"
    assert scorer.received_candidates[0].title == (
        "Incident Timeline Tool"
    )


def test_comparison_artifact_adds_semantic_traces_from_injected_scorer():
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )

    class FakeTrace:
        def to_dict(self):
            return {
                "candidate_key": "semantic-1",
                "candidate_title": "Incident Timeline Tool",
                "raw_cosine": 0.8,
                "normalized_score": 0.9,
                "goal_text_used": "Build an incident project.",
                "candidate_text_used": "Incident Timeline Tool.",
            }

    class FakeResult:
        trace = FakeTrace()

    class FakeScorer:
        def score_candidates(self, request, candidates):
            return [FakeResult()]

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Incident Correlation",
                    "abstract": "Correlate operational incident signals.",
                }
            ],
        },
        user_goal="Build an incident project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Timeline Tool",
                        "problem_statement": "Connect incident signals.",
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load signals.",
                            "Show a timeline.",
                        ],
                        "mvp_scope": [
                            "Load sample records.",
                            "Order records by time.",
                            "Render a timeline.",
                        ],
                        "success_metrics": ["Faster review."],
                        "evidence_relationship": "Uses retained evidence.",
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
        semantic_goal_scorer=FakeScorer(),
    )

    traces = artifact["v2_shadow"]["semantic_goal_relevance"]

    assert traces[0]["candidate_key"] == "semantic-1"
    assert artifact["v2_shadow"]["selected_candidates"][0][
        "title"
    ] == "Incident Timeline Tool"


def test_cross_encoder_shadow_scores_only_low_margin_candidates():
    from planning.shadow_comparison_demo import (
        build_cross_encoder_goal_relevance_shadow,
    )

    class FakeEmbeddingTrace:
        def __init__(self, key, title, raw_cosine):
            self.candidate_key = key
            self.candidate_title = title
            self.raw_cosine = raw_cosine
            self.normalized_score = (raw_cosine + 1.0) / 2.0

    class FakeEmbeddingResult:
        def __init__(self, key, title, raw_cosine):
            self.candidate_key = key
            self.trace = FakeEmbeddingTrace(
                key,
                title,
                raw_cosine,
            )

    class FakeEmbeddingScorer:
        def score_candidates(self, request, candidates):
            return [
                FakeEmbeddingResult("direct", candidates[0].title, 0.70),
                FakeEmbeddingResult(
                    "near_miss",
                    candidates[1].title,
                    0.67,
                ),
                FakeEmbeddingResult("weak", candidates[2].title, 0.40),
            ]

    class FakeCrossEncoderResult:
        def __init__(self, title, raw_score):
            self.candidate_title = title
            self.raw_score = raw_score

    class FakeCrossEncoderScorer:
        def __init__(self):
            self.received_titles = None

        def score_candidates(self, request, candidates):
            self.received_titles = [
                candidate.title for candidate in candidates
            ]
            return [
                FakeCrossEncoderResult(
                    candidate.title,
                    score,
                )
                for candidate, score in zip(
                    candidates,
                    [4.2, 0.8],
                )
            ]

    selected_candidates = [
        {
            "title": "Direct Candidate",
            "problem_statement": "Directly solves the goal.",
            "target_user": "Engineers",
            "core_workflow": [],
            "mvp_scope": [],
            "success_metrics": [],
            "evidence_relationship": "",
            "source_ids": [],
            "assumptions": [],
            "suggested_stack": [],
            "ranking": {"score": 0.9},
        },
        {
            "title": "Near Miss Candidate",
            "problem_statement": "Related but incomplete.",
            "target_user": "Engineers",
            "core_workflow": [],
            "mvp_scope": [],
            "success_metrics": [],
            "evidence_relationship": "",
            "source_ids": [],
            "assumptions": [],
            "suggested_stack": [],
            "ranking": {"score": 0.8},
        },
        {
            "title": "Weak Candidate",
            "problem_statement": "Only loosely related.",
            "target_user": "Engineers",
            "core_workflow": [],
            "mvp_scope": [],
            "success_metrics": [],
            "evidence_relationship": "",
            "source_ids": [],
            "assumptions": [],
            "suggested_stack": [],
            "ranking": {"score": 0.7},
        },
    ]

    cross_encoder_scorer = FakeCrossEncoderScorer()

    traces = build_cross_encoder_goal_relevance_shadow(
        selected_candidates=selected_candidates,
        generation_request=object(),
        embedding_scorer=FakeEmbeddingScorer(),
        cross_encoder_scorer=cross_encoder_scorer,
        top_k=3,
        margin_threshold=0.05,
    )

    assert cross_encoder_scorer.received_titles == [
        "Direct Candidate",
        "Near Miss Candidate",
    ]
    assert [trace["candidate_key"] for trace in traces] == [
        "direct",
        "near_miss",
    ]
    assert traces[0]["cross_encoder_raw_score"] == 4.2
    assert traces[1]["cross_encoder_raw_score"] == 0.8
    assert traces[0]["escalation_reason"] == "within_top_margin"
    assert traces[0]["embedding_rank"] == 1
    assert traces[0]["top_embedding_margin"] == 0.0
    assert traces[0]["cohort_size"] == 3
    assert traces[1]["embedding_rank"] == 2
    assert traces[1]["top_embedding_margin"] == 0.03
    assert traces[0]["embedding_rank"] == 1
    assert traces[0]["top_embedding_margin"] == 0.0
    assert traces[0]["cohort_size"] == 3
    assert traces[1]["embedding_rank"] == 2
    assert traces[1]["top_embedding_margin"] == 0.03


def test_artifact_keeps_cross_encoder_shadow_separate_from_selection():
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )

    class FakeEmbeddingTrace:
        def __init__(self, key, title, raw_cosine):
            self.candidate_key = key
            self.candidate_title = title
            self.raw_cosine = raw_cosine
            self.normalized_score = (raw_cosine + 1.0) / 2.0

        def to_dict(self):
            return {
                "candidate_key": self.candidate_key,
                "candidate_title": self.candidate_title,
                "raw_cosine": self.raw_cosine,
                "normalized_score": self.normalized_score,
            }

    class FakeEmbeddingResult:
        def __init__(self, key, title, raw_cosine):
            self.candidate_key = key
            self.trace = FakeEmbeddingTrace(
                key,
                title,
                raw_cosine,
            )

    class FakeEmbeddingScorer:
        def score_candidates(self, request, candidates):
            return [
                FakeEmbeddingResult(
                    "candidate-1",
                    candidates[0].title,
                    0.70,
                )
            ]

    class FakeCrossEncoderResult:
        def __init__(self, title):
            self.candidate_title = title
            self.raw_score = 4.5

    class FakeCrossEncoderScorer:
        def score_candidates(self, request, candidates):
            return [
                FakeCrossEncoderResult(candidate.title)
                for candidate in candidates
            ]

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Incident Evidence",
                    "abstract": "Operational incident evidence.",
                }
            ],
        },
        user_goal="Build an incident investigation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Timeline",
                        "problem_statement": (
                            "Connect incident evidence."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident records.",
                            "Connect related evidence.",
                        ],
                        "mvp_scope": [
                            "Load sample records.",
                            "Link evidence by incident.",
                            "Show a shared timeline.",
                        ],
                        "success_metrics": [
                            "Faster incident review.",
                        ],
                        "evidence_relationship": (
                            "Uses retained evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": [],
                    }
                ]
            }
        ),
        semantic_goal_scorer=FakeEmbeddingScorer(),
        cross_encoder_goal_scorer=FakeCrossEncoderScorer(),
        cross_encoder_top_k=3,
        cross_encoder_margin_threshold=0.05,
    )

    assert artifact["v2_shadow"]["selected_candidates"][0][
        "title"
    ] == "Incident Timeline"
    assert artifact["v2_shadow"]["semantic_goal_relevance"][0][
        "candidate_key"
    ] == "candidate-1"
    assert artifact["v2_shadow"]["cross_encoder_goal_relevance"] == []


def test_cross_encoder_shadow_requires_semantic_shadow(monkeypatch):
    import pytest
    from types import SimpleNamespace

    from planning import shadow_comparison_demo as demo

    monkeypatch.setattr(
        demo,
        "parse_args",
        lambda: SimpleNamespace(
            semantic_shadow=False,
            cross_encoder_shadow=True,
        ),
    )

    with pytest.raises(
        SystemExit,
        match="--cross-encoder-shadow requires --semantic-shadow",
    ):
        demo.main()


def test_artifact_adds_evidence_support_trace_separately():
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )

    class FakeAssessment:
        def __init__(self, candidate):
            self._candidate = candidate
            self.citation_integrity = {
                "provided_count": 1,
                "valid_count": 1,
                "invalid_count": 0,
                "valid_fraction": 1.0,
            }
            self.direct_citation_count = 1
            self.adjacent_citation_count = 0
            self.uncited_candidate = False
            self.cited_source_alignments = []
            self.warnings = []

        def to_dict(self):
            return {
                "candidate_title": self._candidate.title,
                "citation_integrity": self.citation_integrity,
                "direct_citation_count": self.direct_citation_count,
                "adjacent_citation_count": self.adjacent_citation_count,
                "uncited_candidate": self.uncited_candidate,
                "cited_source_alignments": self.cited_source_alignments,
                "warnings": self.warnings,
            }

    class FakeEvidenceSupportScorer:
        def __init__(self):
            self.received_candidates = None
            self.received_brief = None

        def assess_candidate(self, candidate, brief):
            self.received_candidates = (
                self.received_candidates or []
            ) + [candidate]
            self.received_brief = brief
            return FakeAssessment(candidate)

    scorer = FakeEvidenceSupportScorer()

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Incident Evidence",
                    "abstract": (
                        "Correlate operational events during incidents."
                    ),
                }
            ],
        },
        user_goal="Build an incident investigation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Timeline",
                        "problem_statement": (
                            "Connect operational incident signals."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident records.",
                            "Connect related evidence.",
                        ],
                        "mvp_scope": [
                            "Load sample records.",
                            "Link evidence by incident.",
                            "Show a shared timeline.",
                        ],
                        "success_metrics": [
                            "Faster incident review.",
                        ],
                        "evidence_relationship": (
                            "Uses retained incident evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": [],
                    }
                ]
            }
        ),
        evidence_support_scorer=scorer,
    )

    traces = artifact["v2_shadow"]["evidence_support"]

    assert traces[0]["candidate_title"] == "Incident Timeline"
    assert scorer.received_candidates[0].title == "Incident Timeline"
    assert scorer.received_brief.sources[0].source_id == "paper-1"
    assert artifact["v2_shadow"]["selected_candidates"][0][
        "ranking"
    ]["score"] >= 0.0


def test_evidence_support_shadow_flag_initializes_trace_scorer(monkeypatch):
    from types import SimpleNamespace

    from planning import shadow_comparison_demo as demo

    monkeypatch.setattr(
        demo,
        "parse_args",
        lambda: SimpleNamespace(
            cross_encoder_shadow=False,
            semantic_shadow=False,
            evidence_support_shadow=True,
            provider="mock",
            allow_live_llm=False,
            query="Build an incident investigation project.",
            selected_direction=None,
            skill_level="",
            time_available="",
            target_role=[],
            preferred_stack=[],
            fixture_response=None,
            output_dir="outputs/test_shadow_artifacts",
        ),
    )

    class FakeSemanticEngine:
        pass

    class FakeEvidenceSupportScorer:
        def __init__(self, encoder):
            self.encoder = encoder

    captured = {}

    def fake_build_artifact(**kwargs):
        captured.update(kwargs)
        return {
            "legacy_planner": {"direction_count": 0},
            "v2_shadow": {"status": "prompt_ready"},
        }

    monkeypatch.setattr(demo, "SemanticEngine", FakeSemanticEngine)
    monkeypatch.setattr(
        demo,
        "CandidateEvidenceSupportScorer",
        FakeEvidenceSupportScorer,
    )
    monkeypatch.setattr(
        demo,
        "SemanticEngineTextEncoder",
        lambda engine: ("encoder", engine),
    )
    monkeypatch.setattr(
        demo,
        "retrieve_evidence",
        lambda **kwargs: {
            "inference": {},
            "merged_results": [],
        },
    )
    monkeypatch.setattr(
        demo,
        "build_shadow_comparison_artifact",
        fake_build_artifact,
    )
    monkeypatch.setattr(
        demo,
        "write_shadow_comparison_artifact",
        lambda artifact, output_dir: output_dir / "artifact.json",
    )

    demo.main()

    assert isinstance(
        captured["evidence_support_scorer"],
        FakeEvidenceSupportScorer,
    )


def test_shadow_cli_passes_query_understanding_hints_to_retrieval(
    monkeypatch,
):
    from types import SimpleNamespace

    from planning import shadow_comparison_demo as demo

    query = (
        "Build a developer productivity project that helps engineers "
        "identify flaky tests."
    )

    monkeypatch.setattr(
        demo,
        "parse_args",
        lambda: SimpleNamespace(
            cross_encoder_shadow=False,
            semantic_shadow=False,
            evidence_support_shadow=False,
            provider="mock",
            allow_live_llm=False,
            query=query,
            selected_direction=None,
            skill_level="",
            time_available="",
            target_role=[],
            preferred_stack=[],
            fixture_response=None,
            output_dir="outputs/test_shadow_artifacts",
        ),
    )

    monkeypatch.setattr(
        demo,
        "understand_query",
        lambda goal, constraints: {
            "direction_hints": ["software_engineering"],
        },
        raising=False,
    )

    captured = {}

    def fake_retrieve_evidence(**kwargs):
        captured.update(kwargs)
        return {
            "inference": {},
            "merged_results": [],
        }

    monkeypatch.setattr(
        demo,
        "retrieve_evidence",
        fake_retrieve_evidence,
    )
    monkeypatch.setattr(
        demo,
        "build_shadow_comparison_artifact",
        lambda **kwargs: {
            "legacy_planner": {"direction_count": 0},
            "v2_shadow": {"status": "prompt_ready"},
        },
    )
    monkeypatch.setattr(
        demo,
        "write_shadow_comparison_artifact",
        lambda artifact, output_dir: output_dir / "artifact.json",
    )

    demo.main()

    assert captured["user_query"] == query
    assert captured["intent_hints"] == ["software_engineering"]


def test_shadow_artifact_exposes_grounding_adequacy_from_evidence_support():
    from planning import shadow_comparison_demo as demo
    from planning.mock_generation_provider import MockCandidateGenerationProvider

    class FakeEvidenceSupportScorer:
        def assess_candidate(self, candidate, brief):
            from planning.evidence_support import (
                CandidateEvidenceSupportAssessment,
                CitedSourceAlignment,
            )

            return CandidateEvidenceSupportAssessment(
                candidate_title=candidate.title,
                citation_integrity={
                    "provided_count": 1,
                    "valid_count": 1,
                    "invalid_count": 0,
                    "valid_fraction": 1.0,
                },
                direct_citation_count=1,
                adjacent_citation_count=0,
                uncited_candidate=False,
                cited_source_alignments=[
                    CitedSourceAlignment(
                        source_id="paper-1",
                        source_type="research_paper",
                        support_scope="direct",
                        raw_cosine=0.42,
                        normalized_score=0.71,
                    )
                ],
            )

    artifact = demo.build_shadow_comparison_artifact(
        user_goal="Build an incident investigation project.",
        constraints={},
        evidence_payload={
            "selected_route": "test",
            "expanded_query": "incident investigation",
            "focused_query": "incident investigation",
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Event Correlation for Incidents",
                    "abstract": (
                        "Correlate deployment and service-health events "
                        "during incident investigation."
                    ),
                }
            ],
        },
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Timeline Correlator",
                        "problem_statement": (
                            "Connect deployment and service-health signals."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Ingest incident signals.",
                            "Correlate related events.",
                        ],
                        "mvp_scope": [
                            "Load sample events.",
                            "Correlate related signals.",
                            "Show an incident timeline.",
                        ],
                        "success_metrics": [
                            "Time to identify related events."
                        ],
                        "evidence_relationship": (
                            "Uses event-correlation evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    }
                ]
            }
        ),
        execution_mode="fixture",
        evidence_support_scorer=FakeEvidenceSupportScorer(),
    )

    traces = artifact["v2_shadow"]["grounding_adequacy"]

    assert len(traces) == 1
    assert traces[0]["candidate_title"] == "Incident Timeline Correlator"
    assert traces[0]["adequacy_class"] == "cited_with_direct_scope"
    assert traces[0]["min_cited_alignment"] == 0.42


def test_shadow_artifact_exposes_semantic_candidate_diversity():
    from planning import shadow_comparison_demo as demo
    from planning.mock_generation_provider import MockCandidateGenerationProvider
    from planning.semantic_goal_relevance import EmbeddingVector

    class FakeDiversityScorer:
        def assess_candidates(self, candidates):
            assert len(candidates) == 2

            class Trace:
                def to_dict(self):
                    return {
                        "similarity_threshold": 0.82,
                        "pairwise_similarity": [
                            {
                                "candidate_a_title": candidates[0].title,
                                "candidate_b_title": candidates[1].title,
                                "raw_cosine": 0.91,
                                "flagged": True,
                            }
                        ],
                        "passed": False,
                    }

            return Trace()

    artifact = demo.build_shadow_comparison_artifact(
        user_goal="Build an incident investigation project.",
        constraints={},
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Event Correlation for Incidents",
                    "abstract": "Correlate incident events.",
                }
            ],
        },
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Correlation Dashboard",
                        "problem_statement": "Connect incident signals.",
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load events.",
                            "Correlate signals.",
                        ],
                        "mvp_scope": [
                            "Load records.",
                            "Correlate events.",
                            "Show a dashboard.",
                        ],
                        "success_metrics": ["Faster investigation."],
                        "evidence_relationship": "Uses incident evidence.",
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                    {
                        "title": "Incident Signal Workbench",
                        "problem_statement": "Inspect related incident signals.",
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident records.",
                            "Inspect signal links.",
                        ],
                        "mvp_scope": [
                            "Load records.",
                            "Link signals.",
                            "Show a workbench.",
                        ],
                        "success_metrics": ["Faster investigation."],
                        "evidence_relationship": "Uses incident evidence.",
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                ]
            }
        ),
        execution_mode="fixture",
        semantic_candidate_diversity_scorer=FakeDiversityScorer(),
    )

    trace = artifact["v2_shadow"]["semantic_candidate_diversity"]

    assert trace["passed"] is False
    assert trace["pairwise_similarity"][0]["flagged"] is True


def test_shadow_artifact_exposes_soft_quality_warnings():
    from planning import shadow_comparison_demo as demo

    artifact = demo.build_shadow_comparison_artifact(
        user_goal="Build a cloud incident investigation project.",
        constraints={},
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "repo-1",
                    "source_type": "github_repository",
                    "title": "Cloud Operations Toolkit",
                    "abstract": "Organize cloud operational signals.",
                }
            ],
        },
    )

    warnings = artifact["v2_shadow"]["quality_warnings"]

    assert warnings["signals"]["quality_warning_count"] == 1
    assert warnings["warnings"][0]["code"] == (
        "missing_direct_research_evidence"
    )


def test_shadow_artifact_exposes_per_candidate_promotion_eligibility():
    from planning.evidence_support import (
        CandidateEvidenceSupportScorer,
    )
    from planning.semantic_goal_relevance import EmbeddingVector
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )

    class FakeEncoder:
        def encode_text(self, text):
            return EmbeddingVector((1.0, 0.0))

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Incident Correlation Research",
                    "abstract": (
                        "Event correlation supports incident "
                        "investigation workflows."
                    ),
                }
            ],
        },
        user_goal="Build an incident investigation project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Incident Correlation Workbench",
                        "problem_statement": (
                            "Operational signals are fragmented during "
                            "incident investigation."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident events.",
                            "Correlate related operational signals.",
                        ],
                        "mvp_scope": [
                            "Load representative event records.",
                            "Correlate related incident signals.",
                            "Show an investigation timeline.",
                        ],
                        "success_metrics": [
                            "Reduce time to identify related events."
                        ],
                        "evidence_relationship": (
                            "Uses retained incident correlation evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    }
                ]
            }
        ),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            FakeEncoder()
        ),
    )

    promotion = artifact["v2_shadow"]["promotion_eligibility"]

    assert promotion["status"] == "assessed"
    assert promotion["summary"] == {
        "eligible_count": 1,
        "needs_review_count": 0,
        "ineligible_count": 0,
    }
    assert promotion["candidate_assessments"][0]["status"] == "eligible"
    assert promotion["candidate_assessments"][0][
        "eligible_for_product_promotion"
    ] is True


def test_shadow_artifact_exposes_semantic_diversification_repair_plan():
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )
    from planning.semantic_goal_relevance import EmbeddingVector

    class FakeEncoder:
        def encode_text(self, text):
            if "Monitor" in text:
                return EmbeddingVector((1.0, 0.0))
            return EmbeddingVector((0.8, 0.6))

    from planning.semantic_candidate_diversity import (
        SemanticCandidateDiversityScorer,
    )

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Data Pipeline Quality Research",
                    "abstract": (
                        "Pipeline validation and quality checks improve "
                        "data reliability."
                    ),
                }
            ],
        },
        user_goal="Build a data pipeline quality project.",
        constraints={},
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Pipeline Monitor",
                        "problem_statement": (
                            "Teams need visibility into data quality."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Run data checks.",
                            "Show quality alerts.",
                        ],
                        "mvp_scope": [
                            "Load pipeline records.",
                            "Run validation checks.",
                            "Show alert results.",
                        ],
                        "success_metrics": [
                            "Number of detected quality issues."
                        ],
                        "evidence_relationship": (
                            "Uses retained data quality evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                    {
                        "title": "Pipeline Failure Triage",
                        "problem_statement": (
                            "Teams need faster pipeline quality triage."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Run data checks.",
                            "Review failed records.",
                        ],
                        "mvp_scope": [
                            "Load pipeline records.",
                            "Run validation checks.",
                            "Show failed records.",
                        ],
                        "success_metrics": [
                            "Time to review quality failures."
                        ],
                        "evidence_relationship": (
                            "Uses retained data quality evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                ]
            }
        ),
        semantic_candidate_diversity_scorer=(
            SemanticCandidateDiversityScorer(FakeEncoder())
        ),
    )

    repair = artifact["v2_shadow"][
        "semantic_diversification_repair"
    ]

    assert repair["status"] == "repair_planned"
    assert repair["signals"]["replacement_count"] == 1

    directive = repair["directives"][0]
    ranked_scores = {
        candidate["title"]: candidate["ranking"]["score"]
        for candidate in artifact["v2_shadow"]["selected_candidates"]
    }

    retained_title = directive["retain_candidate_titles"][0]
    replaced_title = directive["replace_candidate_title"]

    assert {retained_title, replaced_title} == {
        "Pipeline Monitor",
        "Pipeline Failure Triage",
    }
    assert ranked_scores[retained_title] >= ranked_scores[replaced_title]


def test_artifact_keeps_complete_enrichment_inputs_for_future_comparison():
    from planning.semantic_goal_relevance import EmbeddingVector

    class FakeEncoder:
        def encode_text(self, text):
            if "timeline" in text.lower():
                return EmbeddingVector((1.0, 0.0))
            return EmbeddingVector((0.0, 1.0))

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {"inferred_focus": "cloud_platform"},
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Incident Correlation Research",
                    "abstract": "Correlate incident events.",
                }
            ],
        },
        user_goal="Build a cloud incident project.",
        constraints={
            "target_roles": ["Platform Engineer"],
            "preferred_stack": [],
            "time_available": "3 weeks",
        },
        fixture_response={
            "candidates": [
                {
                    "title": "Incident Timeline Tool",
                    "problem_statement": "Connect incident signals.",
                    "target_user": "Platform engineers",
                    "core_workflow": [
                        "Load incident events.",
                        "Build a timeline.",
                    ],
                    "mvp_scope": [
                        "Load sample records.",
                        "Order events.",
                        "Show a timeline.",
                    ],
                    "success_metrics": ["Faster review."],
                    "evidence_relationship": "Uses retained evidence.",
                    "source_ids": ["paper-1"],
                    "assumptions": [],
                    "suggested_stack": ["Python", "FastAPI"],
                }
            ]
        },
        comparison_encoder=FakeEncoder(),
    )

    assert artifact["legacy_planner"]["raw_ideas"]
    assert artifact["legacy_planner"]["enrichment"]["ideas"]
    assert artifact["v2_shadow"]["raw_candidates"][0]["title"] == (
        "Incident Timeline Tool"
    )
    assert artifact["v2_shadow"]["enrichment"]["ideas"][0][
        "planner_provenance"
    ]["planning_source"] == "openai"
    assert "shadow_vs_deterministic_comparison" in artifact["v2_shadow"]


def test_shadow_artifact_records_feasibility_prescreen_for_promotion():
    from planning.evidence_support import (
        CandidateEvidenceSupportScorer,
    )
    from planning.mock_generation_provider import (
        MockCandidateGenerationProvider,
    )
    from planning.semantic_goal_relevance import EmbeddingVector

    class FakeEncoder:
        def encode_text(self, text):
            return EmbeddingVector((1.0, 0.0))

    artifact = build_shadow_comparison_artifact(
        evidence_payload={
            "inference": {
                "inferred_focus": "data_engineering",
            },
            "merged_results": [
                {
                    "document_id": "paper-1",
                    "source_type": "research_paper",
                    "title": "Data Quality Research",
                    "abstract": (
                        "Data validation improves pipeline reliability."
                    ),
                }
            ],
        },
        user_goal="Build a data pipeline quality project.",
        constraints={
            "time_available": "weekend",
            "target_roles": ["Data Engineer"],
        },
        provider=MockCandidateGenerationProvider(
            response={
                "candidates": [
                    {
                        "title": "Lineage-Aware Pipeline Impact Explorer",
                        "problem_statement": (
                            "Data engineers need to trace downstream assets "
                            "affected by a quality incident."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load lineage edges.",
                            "Trace affected downstream assets.",
                        ],
                        "mvp_scope": [
                            "Load lineage edges.",
                            "Build an impact graph.",
                            "Trace downstream assets.",
                            "Rank severity.",
                            "Add ownership mapping.",
                            "Show a dashboard.",
                        ],
                        "success_metrics": [
                            "Reduce time to assess incident impact."
                        ],
                        "evidence_relationship": (
                            "Uses retained data-quality evidence."
                        ),
                        "source_ids": ["paper-1"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    }
                ]
            }
        ),
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            FakeEncoder()
        ),
    )

    promotion = artifact["v2_shadow"]["promotion_eligibility"]
    assessment = promotion["candidate_assessments"][0]

    assert assessment["status"] == "ineligible"
    assert assessment["signals"]["feasibility_prescreen"]["status"] == (
        "blocked_by_constraints"
    )
    assert "Candidate scope exceeds the stated timeline." in (
        assessment["blocking_reasons"]
    )
