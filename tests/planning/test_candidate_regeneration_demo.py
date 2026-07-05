import json
from types import SimpleNamespace

from planning.candidate_regeneration_demo import (
    build_regeneration_artifact,
    run_guarded_regeneration,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.regeneration_source_artifact import (
    load_regeneration_source_artifact,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def encode_text(self, text):
        if "Pipeline Monitor" in text:
            return EmbeddingVector((1.0, 0.0))

        if "Schema Drift Detection and Data Contract Guard" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Schema Drift Contract Guard" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Data Quality Research" in text:
            return EmbeddingVector((0.0, 1.0))

        raise AssertionError(f"Unexpected text: {text}")


class FakeRegenerationProvider:
    def __init__(self):
        self.model = "test-model"
        self.last_usage = {
            "input_tokens": 111,
            "output_tokens": 222,
            "total_tokens": 333,
        }
        self.calls = []

    def generate_regeneration(self, prompt, allow_live_llm=False):
        self.calls.append(
            {
                "prompt": prompt,
                "allow_live_llm": allow_live_llm,
            }
        )

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
                    "Uses retained data-quality evidence."
                ),
                "source_ids": ["paper-1"],
                "assumptions": [
                    "The MVP uses versioned sample schemas.",
                ],
                "suggested_stack": ["Python", "FastAPI"],
            }
        }


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


def source_artifact():
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


def test_runs_one_guarded_regeneration_and_builds_artifact(tmp_path):
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source_artifact()))

    source = load_regeneration_source_artifact(source_path)
    provider = FakeRegenerationProvider()
    encoder = ControlledEncoder()

    cycle = run_guarded_regeneration(
        source=source,
        provider=provider,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert len(provider.calls) == 1
    assert provider.calls[0]["allow_live_llm"] is True
    assert "Generate exactly one replacement" in provider.calls[0]["prompt"]
    assert cycle.accepted is True

    artifact = build_regeneration_artifact(
        source=source,
        cycle=cycle,
        provider=provider,
    )

    assert artifact["execution_mode"] == "guarded_live_regeneration"
    assert artifact["replacement_target"]["title"] == (
        "Pipeline Failure Triage"
    )
    assert artifact["cycle"]["accepted"] is True
    assert artifact["generation_metadata"]["usage"]["total_tokens"] == 333


def source_artifact_with_existing_schema_direction():
    payload = source_artifact()
    payload["v2_shadow"]["selected_candidates"].append(
        {
            **candidate("Schema Drift Detection and Data Contract Guard", 0.88),
            "core_workflow": [
                "Compare schemas against a declared contract.",
                "Explain changed fields and downstream impact.",
            ],
            "mvp_scope": [
                "Load schema snapshots.",
                "Compare contract versions.",
                "Show drift findings.",
            ],
        }
    )
    return payload


def test_rejects_regeneration_close_to_non_retained_surviving_candidate(
    tmp_path,
):
    source_path = tmp_path / "source.json"
    source_path.write_text(
        json.dumps(source_artifact_with_existing_schema_direction())
    )

    source = load_regeneration_source_artifact(source_path)
    provider = FakeRegenerationProvider()
    encoder = ControlledEncoder()

    cycle = run_guarded_regeneration(
        source=source,
        provider=provider,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert [
        candidate.title
        for candidate in source.surviving_candidates
    ] == [
        "Pipeline Monitor",
        "Schema Drift Detection and Data Contract Guard",
    ]
    assert cycle.accepted is False
    assert cycle.replacement_evaluation.replacement_status == "rejected"
    assert cycle.replacement_evaluation.reasons == [
        (
            "Replacement candidate remains semantically close to a "
            "retained direction."
        )
    ]
