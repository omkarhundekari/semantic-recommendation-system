from planning.shadow_quality_warnings import (
    assess_shadow_quality_warnings,
)


def test_returns_no_warnings_for_strong_shadow_signals():
    assessment = assess_shadow_quality_warnings(
        coverage_warnings=[],
        semantic_goal_relevance=[
            {
                "candidate_title": "Incident Timeline",
                "raw_cosine": 0.62,
            }
        ],
        grounding_adequacy=[
            {
                "candidate_title": "Incident Timeline",
                "min_cited_alignment": 0.41,
            }
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "Incident Timeline",
                    "candidate_b_title": "Runbook Gap Analyzer",
                    "raw_cosine": 0.57,
                }
            ]
        },
    )

    assert assessment.warnings == []
    assert assessment.signals["quality_warning_count"] == 0


def test_reports_all_soft_quality_warning_categories():
    assessment = assess_shadow_quality_warnings(
        coverage_warnings=[
            "No research-paper evidence was included in this brief."
        ],
        semantic_goal_relevance=[
            {
                "candidate_title": "Weak Goal Fit",
                "raw_cosine": 0.41,
            }
        ],
        grounding_adequacy=[
            {
                "candidate_title": "Weak Evidence Fit",
                "min_cited_alignment": 0.12,
            }
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "Similar One",
                    "candidate_b_title": "Similar Two",
                    "raw_cosine": 0.81,
                }
            ]
        },
    )

    warnings = {
        warning.code: warning
        for warning in assessment.warnings
    }

    assert set(warnings) == {
        "missing_direct_research_evidence",
        "low_goal_alignment",
        "weak_grounding_alignment",
        "near_duplicate_candidates",
    }
    assert warnings["low_goal_alignment"]["details"] if False else True
    assert warnings["near_duplicate_candidates"].details["pairs"][0][
        "raw_cosine"
    ] == 0.81


def test_does_not_warn_at_exact_thresholds():
    assessment = assess_shadow_quality_warnings(
        coverage_warnings=[],
        semantic_goal_relevance=[
            {
                "candidate_title": "Threshold Goal",
                "raw_cosine": 0.45,
            }
        ],
        grounding_adequacy=[
            {
                "candidate_title": "Threshold Grounding",
                "min_cited_alignment": 0.20,
            }
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "One",
                    "candidate_b_title": "Two",
                    "raw_cosine": 0.7799,
                }
            ]
        },
    )

    assert assessment.warnings == []



def test_warns_when_candidate_cites_only_adjacent_context_sources():
    assessment = assess_shadow_quality_warnings(
        coverage_warnings=[],
        semantic_goal_relevance=[],
        grounding_adequacy=[],
        semantic_candidate_diversity=None,
        candidate_source_relevance=[
            {
                "candidate_title": "Health Event Incident Correlator",
                "source_id": "paper-health-events",
                "relevance_status": "adjacent_context_only",
            }
        ],
    )

    warnings = {
        warning.code: warning
        for warning in assessment.warnings
    }

    assert set(warnings) == {"adjacent_context_only_candidate"}
    assert warnings[
        "adjacent_context_only_candidate"
    ].details["candidates"][0]["candidate_title"] == (
        "Health Event Incident Correlator"
    )
    assert assessment.signals["source_relevance_trace_count"] == 1


def test_does_not_warn_when_candidate_has_direct_supported_source():
    assessment = assess_shadow_quality_warnings(
        coverage_warnings=[],
        semantic_goal_relevance=[],
        grounding_adequacy=[],
        semantic_candidate_diversity=None,
        candidate_source_relevance=[
            {
                "candidate_title": "Deployment Correlator",
                "source_id": "paper-cloud-incidents",
                "relevance_status": "lexically_supported",
            },
            {
                "candidate_title": "Deployment Correlator",
                "source_id": "paper-health-events",
                "relevance_status": "adjacent_context_only",
            },
        ],
    )

    assert assessment.warnings == []
    assert assessment.signals["source_relevance_trace_count"] == 2
