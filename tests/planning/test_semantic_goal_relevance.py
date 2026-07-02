import json

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.semantic_goal_relevance import (
    EmbeddingVector,
    GoalRelevanceScorer,
)


class ControlledEncoder:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def encode_text(self, text):
        return EmbeddingVector(
            values=tuple(self.embeddings[text])
        )


def make_candidate(
    title="Candidate",
    problem_statement="Solve a meaningful user problem.",
    target_user="Engineers",
    suggested_stack=None,
):
    return CandidateDirection(
        title=title,
        problem_statement=problem_statement,
        target_user=target_user,
        core_workflow=[
            "Collect input.",
            "Produce a useful result.",
        ],
        mvp_scope=[
            "Load a small sample.",
            "Process the input.",
            "Show the result.",
        ],
        success_metrics=["Useful output quality."],
        evidence_relationship="Uses retained evidence.",
        source_ids=[],
        assumptions=[],
        suggested_stack=suggested_stack or [],
    )


def make_request():
    return CandidateGenerationRequest(
        user_goal="Build a project that helps investigate incidents.",
        target_roles=["Platform Engineer"],
    )


def test_scores_one_result_per_candidate():
    request = make_request()
    first = make_candidate(title="First")
    second = make_candidate(title="Second")

    goal_text = (
        "Build a project that helps investigate incidents. "
        "Target roles: Platform Engineer."
    )
    first_text = (
        "First. Solve a meaningful user problem. Engineers"
    )
    second_text = (
        "Second. Solve a meaningful user problem. Engineers"
    )

    scorer = GoalRelevanceScorer(
        ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                first_text: (1.0, 0.0),
                second_text: (0.0, 1.0),
            }
        )
    )

    results = scorer.score_candidates(
        request,
        [first, second],
    )

    assert len(results) == 2
    assert results[0].score == 1.0
    assert results[1].score == 0.5


def test_opposite_embeddings_normalize_to_zero():
    request = make_request()
    candidate = make_candidate(title="Opposite")

    goal_text = (
        "Build a project that helps investigate incidents. "
        "Target roles: Platform Engineer."
    )
    candidate_text = (
        "Opposite. Solve a meaningful user problem. Engineers"
    )

    scorer = GoalRelevanceScorer(
        ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                candidate_text: (-1.0, 0.0),
            }
        )
    )

    result = scorer.score_candidates(
        request,
        [candidate],
    )[0]

    assert result.score == 0.0
    assert result.trace.raw_cosine == -1.0


def test_trace_shows_exact_text_used_and_excludes_stack_noise():
    request = make_request()
    candidate = make_candidate(
        title="Incident Tool",
        problem_statement="Connect incident evidence.",
        target_user="Platform engineers",
        suggested_stack=["Python", "FastAPI", "Docker"],
    )

    goal_text = (
        "Build a project that helps investigate incidents. "
        "Target roles: Platform Engineer."
    )
    candidate_text = (
        "Incident Tool. Connect incident evidence. "
        "Platform engineers"
    )

    scorer = GoalRelevanceScorer(
        ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                candidate_text: (1.0, 0.0),
            }
        )
    )

    result = scorer.score_candidates(
        request,
        [candidate],
    )[0]

    assert result.trace.goal_text_used == goal_text
    assert result.trace.candidate_text_used == candidate_text
    assert "Python" not in result.trace.candidate_text_used
    assert "FastAPI" not in result.trace.candidate_text_used
    json.dumps(result.trace.to_dict())


def test_candidate_key_is_stable_for_same_candidate():
    request = make_request()
    candidate = make_candidate(title="Stable")

    goal_text = (
        "Build a project that helps investigate incidents. "
        "Target roles: Platform Engineer."
    )
    candidate_text = (
        "Stable. Solve a meaningful user problem. Engineers"
    )

    scorer = GoalRelevanceScorer(
        ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                candidate_text: (1.0, 0.0),
            }
        )
    )

    first = scorer.score_candidates(request, [candidate])[0]
    second = scorer.score_candidates(request, [candidate])[0]

    assert first.candidate_key == second.candidate_key


def test_empty_candidates_returns_empty_result():
    scorer = GoalRelevanceScorer(
        ControlledEncoder({})
    )

    assert scorer.score_candidates(make_request(), []) == []


def test_relevant_candidate_scores_higher_than_unrelated_candidate():
    request = make_request()

    relevant = make_candidate(
        title="Incident Timeline",
        problem_statement=(
            "Connect deployment changes, service health signals, and "
            "operational events during an incident."
        ),
        target_user="Platform engineers",
    )
    unrelated = make_candidate(
        title="Campus Meal Planner",
        problem_statement=(
            "Help students plan meals and generate grocery lists."
        ),
        target_user="Students",
    )

    goal_text = (
        "Build a project that helps investigate incidents. "
        "Target roles: Platform Engineer."
    )
    relevant_text = (
        "Incident Timeline. Connect deployment changes, service health "
        "signals, and operational events during an incident. "
        "Platform engineers"
    )
    unrelated_text = (
        "Campus Meal Planner. Help students plan meals and generate "
        "grocery lists. Students"
    )

    scorer = GoalRelevanceScorer(
        ControlledEncoder(
            {
                goal_text: (1.0, 0.0),
                relevant_text: (0.9, 0.1),
                unrelated_text: (0.0, 1.0),
            }
        )
    )

    results = scorer.score_candidates(
        request,
        [relevant, unrelated],
    )

    assert results[0].trace.candidate_title == "Incident Timeline"
    assert results[0].trace.raw_cosine > results[1].trace.raw_cosine
    assert results[0].score > results[1].score
