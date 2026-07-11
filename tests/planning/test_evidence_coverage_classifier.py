from planning.evidence_coverage_classifier import (
    ADJACENT_ONLY,
    ADEQUATE_DIRECT,
    CROSS_DOMAIN,
    EXPLORATORY,
    OUT_OF_DOMAIN,
    QUERY_TOO_BROAD,
    STRONG_DIRECT,
    classify_evidence_coverage,
)


def direct_card(source_id):
    return {
        "source_id": source_id,
        "support_scope": "direct",
        "evidence_confidence": "Strong",
        "relevance_signal": "plausible",
    }


def adjacent_card(source_id):
    return {
        "source_id": source_id,
        "support_scope": "adjacent_planning",
        "evidence_confidence": "Exploratory",
        "relevance_signal": "plausible",
    }


def weak_card(source_id):
    return {
        "source_id": source_id,
        "support_scope": "direct",
        "evidence_confidence": "Exploratory",
        "relevance_signal": "weak",
    }


def test_strong_direct_coverage_requires_three_unique_direct_cards():
    report = classify_evidence_coverage(
        [direct_card("a"), direct_card("b"), direct_card("c")],
        detected_domain="rag_llm",
        supported_domains={"rag_llm"},
    )

    assert report.coverage_state == STRONG_DIRECT
    assert report.can_generate_directions is True
    assert report.direct_count == 3
    assert report.unique_source_count == 3


def test_adequate_direct_coverage_handles_small_direct_evidence():
    report = classify_evidence_coverage(
        [direct_card("a")],
        detected_domain="cloud",
        supported_domains={"cloud"},
    )

    assert report.coverage_state == ADEQUATE_DIRECT
    assert report.can_generate_directions is True
    assert "limited_direct_evidence" in report.warnings


def test_adjacent_only_coverage_is_labeled_with_caveats():
    report = classify_evidence_coverage(
        [adjacent_card("a"), adjacent_card("b")],
        detected_domain="fintech",
        supported_domains={"fintech"},
    )

    assert report.coverage_state == ADJACENT_ONLY
    assert report.can_generate_directions is True
    assert report.should_offer_exploratory_mode is True


def test_exploratory_coverage_blocks_confident_generation():
    report = classify_evidence_coverage(
        [weak_card("a")],
        detected_domain="robotics",
        supported_domains={"robotics"},
    )

    assert report.coverage_state == EXPLORATORY
    assert report.can_generate_directions is False
    assert report.should_offer_exploratory_mode is True


def test_out_of_domain_coverage_blocks_fake_confidence():
    report = classify_evidence_coverage(
        [],
        detected_domain="ar_vr",
        supported_domains={"rag_llm", "cloud", "frontend"},
    )

    assert report.coverage_state == OUT_OF_DOMAIN
    assert report.can_generate_directions is False
    assert report.should_offer_exploratory_mode is True


def test_query_too_broad_asks_for_clarification_first():
    report = classify_evidence_coverage(
        [direct_card("a"), direct_card("b"), direct_card("c")],
        query_metadata={"query_too_broad": True},
    )

    assert report.coverage_state == QUERY_TOO_BROAD
    assert report.can_generate_directions is False
    assert report.should_ask_clarification is True


def test_cross_domain_query_is_detected_from_domain_inference():
    report = classify_evidence_coverage(
        [direct_card("a"), direct_card("b")],
        domain_inference={
            "candidate_family_count": 2,
            "family_confidence": 0.42,
        },
    )

    assert report.coverage_state == CROSS_DOMAIN
    assert report.can_generate_directions is True
    assert "cross_domain_query" in report.warnings

def test_query_alignment_prevents_unrelated_retrieval_from_becoming_direct():
    cards = [
        {
            "source_id": "movie-rec",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "Movie Recommendation System with Explanation Layer",
            "key_excerpt": "Ranking and personalization for movie recommendations.",
        },
        {
            "source_id": "rag-repo",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "RAGFlow",
            "key_excerpt": "Retrieval augmented generation engine for enterprise documents.",
        },
        {
            "source_id": "ar-paper",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "Visual and Audio Hints for Search Tasks in Augmented Reality",
            "key_excerpt": "An AR approach using head-mounted displays and virtual objects.",
        },
    ]

    report = classify_evidence_coverage(
        cards,
        query="AR VR education project",
        detected_domain="education_tech",
        supported_domains={"education_tech"},
    )

    assert report.coverage_state == ADEQUATE_DIRECT
    assert report.direct_count == 1
    assert report.adjacent_count == 2


def test_query_alignment_keeps_matching_rag_sources_direct():
    cards = [
        {
            "source_id": "rag-a",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "Retrieval-Augmented Generation for Question Answering",
            "key_excerpt": "A RAG workflow for question answering and retrieval evaluation.",
        },
        {
            "source_id": "rag-b",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "RAG Evaluation with Faithfulness Metrics",
            "key_excerpt": "Evaluates answer faithfulness and retrieval quality.",
        },
        {
            "source_id": "rag-c",
            "support_scope": "direct",
            "evidence_confidence": "Strong",
            "relevance_signal": "plausible",
            "title": "Generation-Augmented Retrieval",
            "key_excerpt": "Retrieval and generation methods for QA systems.",
        },
    ]

    report = classify_evidence_coverage(
        cards,
        query="retrieval augmented generation for question answering",
        detected_domain="rag_llm",
        supported_domains={"rag_llm"},
    )

    assert report.coverage_state == STRONG_DIRECT
    assert report.direct_count == 3

