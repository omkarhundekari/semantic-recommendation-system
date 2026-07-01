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
