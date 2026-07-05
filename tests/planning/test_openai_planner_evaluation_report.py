import json

from planning.openai_planner_evaluation_report import (
    build_openai_planner_evaluation_report,
)


def test_report_tracks_evaluated_and_missing_cases(tmp_path):
    user_goal = "Build a RAG evaluation project."

    artifact = {
        "generated_at_utc": "20260705T130257Z",
        "query": user_goal,
        "v2_shadow": {
            "generation_metadata": {
                "execution_mode": "live",
                "model": "test-model",
            },
            "diagnostics": {
                "provider_called": True,
                "valid_candidate_count": 3,
            },
            "shadow_readiness": {"status": "ready"},
            "semantic_candidate_diversity": {"passed": True},
            "semantic_goal_relevance": [
                {"raw_cosine": 0.7},
                {"raw_cosine": 0.8},
            ],
            "grounding_adequacy": [
                {
                    "adequacy_class": "cited_with_direct_scope",
                    "min_cited_alignment": 0.4,
                }
            ],
        },
    }

    (tmp_path / "rag.json").write_text(json.dumps(artifact))

    dataset = {
        "cases": [
            {
                "id": "rag_quality",
                "user_goal": user_goal,
                "manual_review": {
                    "verdict": None,
                    "reason": None,
                },
            },
            {
                "id": "security_triage",
                "user_goal": "Build a security triage project.",
                "manual_review": {
                    "verdict": None,
                    "reason": None,
                },
            },
        ]
    }

    report = build_openai_planner_evaluation_report(
        dataset=dataset,
        output_dir=tmp_path,
    )

    assert report["summary"]["configured_case_count"] == 2
    assert report["summary"]["evaluated_case_count"] == 1
    assert report["summary"]["missing_artifact_case_count"] == 1
    assert report["summary"]["ready_case_count"] == 1
    assert report["summary"]["diversity_pass_case_count"] == 1

    rag = report["case_reports"]["rag_quality"]
    assert rag["status"] == "evaluated"
    assert rag["quality_warnings"]["warnings"] == []
    assert rag["quality_warnings"]["signals"][
        "quality_warning_count"
    ] == 0
    assert rag["goal_relevance_summary"]["minimum_raw_cosine"] == 0.7
    assert rag["goal_relevance_summary"]["average_raw_cosine"] == 0.75
    assert rag["grounding_summary"]["minimum_cited_alignment"] == 0.4
    assert rag["grounding_summary"]["average_cited_alignment"] == 0.4
    assert rag["diversity_summary"]["highest_pair_similarity"] is None

    assert report["summary"]["average_case_goal_relevance"] == 0.75
    assert report["summary"]["minimum_candidate_goal_relevance"] == 0.7
    assert report["summary"]["average_case_grounding_alignment"] == 0.4
    assert report["summary"]["minimum_candidate_grounding_alignment"] == 0.4
    assert report["summary"]["highest_candidate_pair_similarity"] is None
    assert report["summary"]["total_tokens"] == 0
    assert report["summary"]["quality_warning_case_count"] == 0
    assert report["summary"]["quality_warning_counts"] == {}

    missing = report["case_reports"]["security_triage"]
    assert missing["status"] == "missing_artifact"
