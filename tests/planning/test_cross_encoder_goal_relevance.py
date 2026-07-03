from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.cross_encoder_goal_relevance import (
    CrossEncoderGoalRelevanceScorer,
)


class FakePairScorer:
    def __init__(self):
        self.goal_text = None
        self.candidate_texts = None

    def score_pairs(self, goal_text, candidate_texts):
        self.goal_text = goal_text
        self.candidate_texts = list(candidate_texts)
        return [3.4, 1.2]


def make_candidate(
    title,
    problem_statement,
    target_user,
):
    return CandidateDirection(
        title=title,
        problem_statement=problem_statement,
        target_user=target_user,
        core_workflow=[],
        mvp_scope=[],
        success_metrics=[],
        evidence_relationship="",
    )


def test_scores_candidates_with_shared_goal_and_candidate_text():
    pair_scorer = FakePairScorer()
    scorer = CrossEncoderGoalRelevanceScorer(pair_scorer)

    request = CandidateGenerationRequest(
        user_goal="Diagnose unsupported RAG answers.",
        target_roles=["ML Engineer"],
    )
    candidates = [
        make_candidate(
            "Evidence Evaluator",
            "Check whether answers are grounded in retrieved evidence.",
            "ML engineers building RAG systems",
        ),
        make_candidate(
            "Prompt Workspace",
            "Manage prompt versions for RAG applications.",
            "Teams building RAG applications",
        ),
    ]

    results = scorer.score_candidates(request, candidates)

    assert [result.raw_score for result in results] == [3.4, 1.2]
    assert pair_scorer.goal_text == (
        "Diagnose unsupported RAG answers. "
        "Target roles: ML Engineer."
    )
    assert pair_scorer.candidate_texts == [
        (
            "Evidence Evaluator. Check whether answers are grounded "
            "in retrieved evidence. ML engineers building RAG systems"
        ),
        (
            "Prompt Workspace. Manage prompt versions for RAG "
            "applications. Teams building RAG applications"
        ),
    ]


def test_empty_candidates_skip_pair_scoring():
    pair_scorer = FakePairScorer()
    scorer = CrossEncoderGoalRelevanceScorer(pair_scorer)

    results = scorer.score_candidates(
        CandidateGenerationRequest(user_goal="Any goal."),
        [],
    )

    assert results == []
    assert pair_scorer.goal_text is None
