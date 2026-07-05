import json

import pytest

from planning.regeneration_source_artifact import (
    load_regeneration_source_artifact,
)


def candidate(title, score):
    return {
        "title": title,
        "problem_statement": "Teams need a reliable workflow.",
        "target_user": "Data engineers",
        "core_workflow": [
            "Load pipeline records.",
            "Analyze recurring quality issues.",
        ],
        "mvp_scope": [
            "Load sample records.",
            "Analyze failure patterns.",
            "Show a review summary.",
        ],
        "success_metrics": ["Issues are easier to prioritize."],
        "evidence_relationship": "Uses retained data-quality evidence.",
        "source_ids": ["paper-1"],
        "assumptions": [],
        "suggested_stack": ["Python", "FastAPI"],
        "ranking": {"score": score},
    }


def artifact():
    return {
        "query": "Build a data pipeline quality project.",
        "constraints": {
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "target_roles": ["Data Engineer"],
            "preferred_stack": ["Python", "FastAPI"],
        },
        "v2_shadow": {
            "report": {
                "evidence_brief": {
                    "query": "Build a data pipeline quality project.",
                    "sources": [
                        {
                            "source_id": "paper-1",
                            "source_type": "research_paper",
                            "title": "Data Quality Research",
                            "excerpt": "Validation improves reliability.",
                            "support_scope": "direct",
                        }
                    ],
                }
            },
            "selected_candidates": [
                candidate("Pipeline Monitor", 0.93),
                candidate("Pipeline Failure Triage", 0.84),
            ],
            "semantic_candidate_diversity": {
                "similarity_threshold": 0.82,
                "pairwise_similarity": [
                    {
                        "candidate_a_title": "Pipeline Monitor",
                        "candidate_b_title": (
                            "Pipeline Failure Triage"
                        ),
                        "raw_cosine": 0.7915,
                        "flagged": False,
                    }
                ],
                "passed": True,
            },
        },
    }


def test_rebuilds_regeneration_context_from_older_artifact(tmp_path):
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact()))

    context = load_regeneration_source_artifact(path)

    assert context.request.user_goal == (
        "Build a data pipeline quality project."
    )
    assert context.request.time_available == "3 weeks"
    assert context.directive.replace_candidate_title == (
        "Pipeline Failure Triage"
    )
    assert context.directive.retain_candidate_titles == [
        "Pipeline Monitor"
    ]
    assert context.replaced_candidate.title == (
        "Pipeline Failure Triage"
    )
    assert [item.title for item in context.retained_candidates] == [
        "Pipeline Monitor"
    ]
    assert context.brief.sources[0].source_id == "paper-1"


def test_rejects_artifact_without_repair_directives(tmp_path):
    payload = artifact()
    payload["v2_shadow"]["semantic_candidate_diversity"] = {
        "pairwise_similarity": [],
        "passed": True,
    }

    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="no diversification repair"):
        load_regeneration_source_artifact(path)


def test_keeps_all_surviving_candidates_for_replacement_comparison(
    tmp_path,
):
    payload = artifact()
    payload["v2_shadow"]["selected_candidates"].append(
        candidate("Schema Drift Guard", 0.88)
    )

    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(payload))

    context = load_regeneration_source_artifact(path)

    assert [item.title for item in context.retained_candidates] == [
        "Pipeline Monitor"
    ]
    assert [item.title for item in context.surviving_candidates] == [
        "Pipeline Monitor",
        "Schema Drift Guard",
    ]
