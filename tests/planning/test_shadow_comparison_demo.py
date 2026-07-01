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
