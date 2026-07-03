from planning.cross_encoder_goal_adapter import (
    CrossEncoderGoalPairScorer,
)


class FakeModel:
    def __init__(self):
        self.received_pairs = None

    def predict(self, pairs):
        self.received_pairs = pairs
        return [0.72, 0.31]


class FakeReranker:
    def __init__(self):
        self.model = FakeModel()

    def rerank(self, query, documents):
        raise AssertionError(
            "Planning adapter must not call retrieval rerank()."
        )


def test_scores_goal_candidate_pairs_without_retrieval_mutation():
    reranker = FakeReranker()
    scorer = CrossEncoderGoalPairScorer(reranker)

    scores = scorer.score_pairs(
        goal_text="Diagnose unsupported RAG answers.",
        candidate_texts=[
            "Evaluate evidence grounding for generated answers.",
            "Manage prompt versions for RAG applications.",
        ],
    )

    assert scores == [0.72, 0.31]
    assert reranker.model.received_pairs == [
        [
            "Diagnose unsupported RAG answers.",
            "Evaluate evidence grounding for generated answers.",
        ],
        [
            "Diagnose unsupported RAG answers.",
            "Manage prompt versions for RAG applications.",
        ],
    ]


def test_empty_candidate_texts_skip_model_prediction():
    reranker = FakeReranker()
    scorer = CrossEncoderGoalPairScorer(reranker)

    assert scorer.score_pairs(
        goal_text="Any goal.",
        candidate_texts=[],
    ) == []

    assert reranker.model.received_pairs is None
