from planning.semantic_goal_evaluation import (
    evaluate_labeled_ranking,
)


def test_evaluate_labeled_ranking_counts_correct_ordered_pairs():
    report = evaluate_labeled_ranking(
        scored_candidates=[
            {
                "candidate_id": "relevant",
                "label": 2,
                "raw_cosine": 0.82,
            },
            {
                "candidate_id": "adjacent",
                "label": 1,
                "raw_cosine": 0.51,
            },
            {
                "candidate_id": "unrelated",
                "label": 0,
                "raw_cosine": 0.08,
            },
        ]
    )

    assert report["ordered_pair_count"] == 3
    assert report["correct_pair_count"] == 3
    assert report["tie_pair_count"] == 0
    assert report["pairwise_accuracy"] == 1.0
    assert report["top_candidate_id"] == "relevant"
    assert report["top_candidate_label"] == 2


def test_evaluate_labeled_ranking_reports_incorrect_ordering():
    report = evaluate_labeled_ranking(
        scored_candidates=[
            {
                "candidate_id": "relevant",
                "label": 2,
                "raw_cosine": 0.30,
            },
            {
                "candidate_id": "unrelated",
                "label": 0,
                "raw_cosine": 0.75,
            },
        ]
    )

    assert report["ordered_pair_count"] == 1
    assert report["correct_pair_count"] == 0
    assert report["pairwise_accuracy"] == 0.0
    assert report["top_candidate_id"] == "unrelated"


def test_evaluate_labeled_ranking_tracks_ties_separately():
    report = evaluate_labeled_ranking(
        scored_candidates=[
            {
                "candidate_id": "relevant",
                "label": 2,
                "raw_cosine": 0.50,
            },
            {
                "candidate_id": "unrelated",
                "label": 0,
                "raw_cosine": 0.50,
            },
        ]
    )

    assert report["ordered_pair_count"] == 1
    assert report["correct_pair_count"] == 0
    assert report["tie_pair_count"] == 1
    assert report["pairwise_accuracy"] == 0.0


def test_evaluate_labeled_rankings_aggregates_multiple_goals():
    from planning.semantic_goal_evaluation import (
        evaluate_labeled_rankings,
    )

    report = evaluate_labeled_rankings(
        rankings={
            "incident_response": [
                {
                    "candidate_id": "incident",
                    "label": 2,
                    "raw_cosine": 0.9,
                },
                {
                    "candidate_id": "meal",
                    "label": 0,
                    "raw_cosine": 0.1,
                },
            ],
            "frontend_accessibility": [
                {
                    "candidate_id": "accessible_ui",
                    "label": 2,
                    "raw_cosine": 0.8,
                },
                {
                    "candidate_id": "database_backup",
                    "label": 0,
                    "raw_cosine": 0.2,
                },
            ],
        }
    )

    assert report["evaluated_goal_count"] == 2
    assert report["total_ordered_pair_count"] == 2
    assert report["total_correct_pair_count"] == 2
    assert report["overall_pairwise_accuracy"] == 1.0
    assert report["goal_reports"]["incident_response"]["top_candidate_id"] == (
        "incident"
    )


def test_evaluate_semantic_goal_dataset_scores_each_labeled_candidate():
    from planning.semantic_goal_evaluation import (
        evaluate_semantic_goal_dataset,
    )
    from planning.semantic_goal_relevance import (
        EmbeddingVector,
    )

    class ControlledEncoder:
        def __init__(self, embeddings):
            self.embeddings = embeddings

        def encode_text(self, text):
            return EmbeddingVector(
                values=tuple(self.embeddings[text])
            )

    dataset = {
        "cases": [
            {
                "id": "incident_response",
                "user_goal": "Build an incident investigation project.",
                "target_roles": ["Platform Engineer"],
                "candidates": [
                    {
                        "id": "incident_timeline",
                        "label": 2,
                        "title": "Incident Timeline",
                        "problem_statement": (
                            "Connect operational events during incidents."
                        ),
                        "target_user": "Platform engineers",
                    },
                    {
                        "id": "meal_planner",
                        "label": 0,
                        "title": "Meal Planner",
                        "problem_statement": (
                            "Help students plan weekly meals."
                        ),
                        "target_user": "Students",
                    },
                ],
            }
        ]
    }

    goal_text = (
        "Build an incident investigation project. "
        "Target roles: Platform Engineer."
    )
    incident_text = (
        "Incident Timeline. Connect operational events during incidents. "
        "Platform engineers"
    )
    meal_text = (
        "Meal Planner. Help students plan weekly meals. Students"
    )

    report = evaluate_semantic_goal_dataset(
        dataset=dataset,
        encoder=ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                incident_text: (0.9, 0.1),
                meal_text: (0.0, 1.0),
            }
        ),
    )

    assert report["evaluated_goal_count"] == 1
    assert report["overall_pairwise_accuracy"] == 1.0
    assert report["goal_reports"]["incident_response"][
        "top_candidate_id"
    ] == "incident_timeline"


def test_evaluate_labeled_ranking_supports_a_custom_score_field():
    report = evaluate_labeled_ranking(
        scored_candidates=[
            {
                "candidate_id": "direct",
                "label": 2,
                "cross_encoder_score": 4.2,
            },
            {
                "candidate_id": "near_miss",
                "label": 1,
                "cross_encoder_score": 0.5,
            },
            {
                "candidate_id": "unrelated",
                "label": 0,
                "cross_encoder_score": -8.0,
            },
        ],
        score_field="cross_encoder_score",
    )

    assert report["ordered_pair_count"] == 3
    assert report["correct_pair_count"] == 3
    assert report["pairwise_accuracy"] == 1.0
    assert report["top_candidate_id"] == "direct"


def test_evaluate_cross_encoder_goal_dataset_uses_shared_labels():
    from planning.semantic_goal_evaluation import (
        evaluate_cross_encoder_goal_dataset,
    )

    class FakePairScorer:
        def score_pairs(self, goal_text, candidate_texts):
            assert goal_text == "Diagnose unsupported RAG answers."
            assert candidate_texts == [
                "Evidence Evaluator. Check answer grounding. ML engineers",
                "Prompt Workspace. Manage prompt versions. RAG teams",
            ]
            return [4.0, 0.2]

    dataset = {
        "cases": [
            {
                "id": "rag_quality",
                "user_goal": "Diagnose unsupported RAG answers.",
                "candidates": [
                    {
                        "id": "evidence_evaluator",
                        "label": 2,
                        "title": "Evidence Evaluator",
                        "problem_statement": "Check answer grounding.",
                        "target_user": "ML engineers",
                    },
                    {
                        "id": "prompt_workspace",
                        "label": 1,
                        "title": "Prompt Workspace",
                        "problem_statement": "Manage prompt versions.",
                        "target_user": "RAG teams",
                    },
                ],
            }
        ]
    }

    report = evaluate_cross_encoder_goal_dataset(
        dataset=dataset,
        pair_scorer=FakePairScorer(),
    )

    assert report["score_field"] == "cross_encoder_score"
    assert report["evaluated_goal_count"] == 1
    assert report["overall_pairwise_accuracy"] == 1.0
    assert report["goal_reports"]["rag_quality"][
        "top_candidate_id"
    ] == "evidence_evaluator"
