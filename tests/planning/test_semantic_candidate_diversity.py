from planning.candidate_models import CandidateDirection
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
    build_diversity_text,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def __init__(self, embeddings):
        self.embeddings = embeddings

    def encode_text(self, text):
        return EmbeddingVector(values=tuple(self.embeddings[text]))


def make_candidate(title, problem):
    return CandidateDirection(
        title=title,
        problem_statement=problem,
        target_user="ML engineers",
        core_workflow=[
            "Load evaluation records.",
            "Inspect quality signals.",
        ],
        mvp_scope=[
            "Load sample data.",
            "Compute quality scores.",
            "Show a review screen.",
        ],
        success_metrics=["Useful diagnostics."],
        evidence_relationship="Uses retained evidence.",
        source_ids=["paper-1"],
    )


def test_flags_semantically_near_duplicate_candidates():
    first = make_candidate(
        "RAG Evaluation Dashboard",
        "Compare RAG runs and investigate quality regressions.",
    )
    second = make_candidate(
        "RAG Quality Regression Console",
        "Inspect RAG quality regressions across model runs.",
    )
    distinct = make_candidate(
        "Citation Coverage Inspector",
        "Show whether answer claims are supported by retrieved evidence.",
    )

    first_text = build_diversity_text(first)
    second_text = build_diversity_text(second)
    distinct_text = build_diversity_text(distinct)

    scorer = SemanticCandidateDiversityScorer(
        ControlledEncoder(
            {
                first_text: (1.0, 0.0),
                second_text: (0.96, 0.04),
                distinct_text: (0.0, 1.0),
            }
        )
    )

    trace = scorer.assess_candidates(
        [first, second, distinct],
        similarity_threshold=0.82,
    )

    assert trace.passed is False
    assert len(trace.pairwise_similarity) == 3

    flagged_pairs = [
        pair
        for pair in trace.pairwise_similarity
        if pair.flagged
    ]

    assert len(flagged_pairs) == 1
    assert flagged_pairs[0].candidate_a_title == (
        "RAG Evaluation Dashboard"
    )
    assert flagged_pairs[0].candidate_b_title == (
        "RAG Quality Regression Console"
    )


def test_allows_distinct_candidate_set():
    first = make_candidate(
        "RAG Evaluation Dashboard",
        "Compare RAG runs and identify quality regressions.",
    )
    second = make_candidate(
        "Retrieval Debugging Console",
        "Inspect chunk retrieval coverage and ranking failures.",
    )
    third = make_candidate(
        "Citation Support Inspector",
        "Check whether answer claims are grounded in retrieved evidence.",
    )

    texts = [
        build_diversity_text(candidate)
        for candidate in [first, second, third]
    ]

    scorer = SemanticCandidateDiversityScorer(
        ControlledEncoder(
            {
                texts[0]: (1.0, 0.0, 0.0),
                texts[1]: (0.0, 1.0, 0.0),
                texts[2]: (0.0, 0.0, 1.0),
            }
        )
    )

    trace = scorer.assess_candidates(
        [first, second, third],
        similarity_threshold=0.82,
    )

    assert trace.passed is True
    assert not any(
        pair.flagged
        for pair in trace.pairwise_similarity
    )
