from types import SimpleNamespace

from planning.semantic_goal_evaluation_report import (
    build_semantic_goal_evaluation_report,
)


class FakeEmbeddingScorer:
    def score_candidates(self, request, candidates):
        scores_by_title = {
            "Evidence Evaluator": 0.80,
            "Prompt Workspace": 0.77,
            "Workout Tracker": 0.10,
        }

        return [
            SimpleNamespace(
                candidate_key=candidate.title,
                trace=SimpleNamespace(
                    raw_cosine=scores_by_title[candidate.title],
                    normalized_score=(
                        scores_by_title[candidate.title] + 1.0
                    )
                    / 2.0,
                ),
            )
            for candidate in candidates
        ]


class FakeCrossEncoderScorer:
    def __init__(self):
        self.received_titles = []

    def score_candidates(self, request, candidates):
        self.received_titles = [
            candidate.title for candidate in candidates
        ]

        scores_by_title = {
            "Evidence Evaluator": 4.5,
            "Prompt Workspace": 0.4,
        }

        return [
            SimpleNamespace(
                raw_score=scores_by_title[candidate.title]
            )
            for candidate in candidates
        ]


def test_report_escalates_only_ambiguous_candidate_cohort():
    cross_encoder = FakeCrossEncoderScorer()

    dataset = {
        "schema_version": 1,
        "cases": [
            {
                "id": "rag_quality",
                "user_goal": (
                    "Diagnose unsupported retrieval-augmented "
                    "generation answers."
                ),
                "target_roles": ["ML Engineer"],
                "candidates": [
                    {
                        "id": "evidence_evaluator",
                        "label": 2,
                        "title": "Evidence Evaluator",
                        "problem_statement": (
                            "Evaluate answer grounding in retrieved evidence."
                        ),
                        "target_user": "ML engineers",
                    },
                    {
                        "id": "prompt_workspace",
                        "label": 1,
                        "title": "Prompt Workspace",
                        "problem_statement": (
                            "Manage prompt versions for RAG systems."
                        ),
                        "target_user": "RAG teams",
                    },
                    {
                        "id": "workout_tracker",
                        "label": 0,
                        "title": "Workout Tracker",
                        "problem_statement": (
                            "Track workouts and fitness goals."
                        ),
                        "target_user": "Gym users",
                    },
                ],
            }
        ],
    }

    report = build_semantic_goal_evaluation_report(
        dataset=dataset,
        embedding_scorer=FakeEmbeddingScorer(),
        cross_encoder_scorer=cross_encoder,
        top_k=3,
        margin_threshold=0.05,
    )

    case_report = report["case_reports"]["rag_quality"]

    assert cross_encoder.received_titles == [
        "Evidence Evaluator",
        "Prompt Workspace",
    ]
    assert case_report["embedding"]["top_candidate_id"] == (
        "evidence_evaluator"
    )
    assert case_report["escalated_candidate_ids"] == [
        "evidence_evaluator",
        "prompt_workspace",
    ]
    assert case_report["cross_encoder"]["top_candidate_id"] == (
        "evidence_evaluator"
    )
    assert report["summary"]["evaluated_case_count"] == 1
    assert report["summary"]["escalated_case_count"] == 1


def test_format_report_summary_shows_metrics_and_routing():
    from planning.semantic_goal_evaluation_report import (
        format_semantic_goal_evaluation_summary,
    )

    report = {
        "routing_policy": {
            "top_k": 3,
            "margin_threshold": 0.05,
        },
        "case_reports": {
            "rag_quality": {
                "embedding": {
                    "pairwise_accuracy": 1.0,
                    "top_candidate_id": "evidence_evaluator",
                    "top_candidate_label": 2,
                },
                "escalated_candidate_ids": [
                    "evidence_evaluator",
                    "prompt_workspace",
                ],
                "cross_encoder": {
                    "pairwise_accuracy": 1.0,
                    "top_candidate_id": "evidence_evaluator",
                    "top_candidate_label": 2,
                },
            }
        },
        "summary": {
            "evaluated_case_count": 1,
            "escalated_case_count": 1,
            "embedding_evaluation": {
                "overall_pairwise_accuracy": 1.0,
            },
            "cross_encoder_evaluation": {
                "overall_pairwise_accuracy": 1.0,
            },
        },
    }

    output = format_semantic_goal_evaluation_summary(report)

    assert "Semantic goal evaluation report" in output
    assert "rag_quality" in output
    assert "embedding_accuracy=1.0000" in output
    assert "escalated=evidence_evaluator, prompt_workspace" in output
    assert "cross_encoder_accuracy=1.0000" in output
    assert "cases=1" in output
