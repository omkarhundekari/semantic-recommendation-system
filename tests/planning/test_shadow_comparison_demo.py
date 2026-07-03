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
