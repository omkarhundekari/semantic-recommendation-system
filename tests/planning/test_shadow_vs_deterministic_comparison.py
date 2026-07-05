from planning.candidate_models import CandidateDirection
from planning.semantic_goal_relevance import EmbeddingVector
from planning.shadow_vs_deterministic_comparison import (
    build_query_fingerprint,
    build_shadow_vs_deterministic_comparison,
)


class FakeEncoder:
    def encode_text(self, text):
        normalized = text.lower()

        if "timeline" in normalized:
            return EmbeddingVector((1.0, 0.0))

        if "lineage" in normalized or "blast radius" in normalized:
            return EmbeddingVector((0.0, 1.0))

        return EmbeddingVector((0.7, 0.7))


def make_candidate(title, workflow):
    return CandidateDirection(
        title=title,
        problem_statement="Platform teams need better incident workflows.",
        target_user="platform engineers",
        core_workflow=[workflow],
        mvp_scope=[
            "Load representative records.",
            "Show an investigation result.",
        ],
        success_metrics=["Faster investigation."],
        evidence_relationship="Uses directly retained evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def test_query_fingerprint_is_stable_for_constraint_key_order():
    first = build_query_fingerprint(
        "Build a cloud incident project.",
        {
            "target_roles": ["Platform Engineer"],
            "time_available": "3 weeks",
        },
    )
    second = build_query_fingerprint(
        "Build a cloud incident project.",
        {
            "time_available": "3 weeks",
            "target_roles": ["Platform Engineer"],
        },
    )

    assert first == second
    assert len(first) == 16


def test_comparison_counts_only_semantically_unique_openai_angles():
    deterministic = [
        make_candidate(
            "Incident Timeline Correlator",
            "Build a deployment-to-incident timeline.",
        )
    ]
    openai = [
        make_candidate(
            "Incident Timeline Explorer",
            "Build an incident timeline for operations.",
        ),
        make_candidate(
            "Lineage Blast Radius Explorer",
            "Trace lineage-aware downstream impact.",
        ),
    ]

    comparison = build_shadow_vs_deterministic_comparison(
        user_goal="Build a cloud incident project.",
        constraints={"time_available": "3 weeks"},
        deterministic_candidates=deterministic,
        openai_candidates=openai,
        openai_grounding_adequacy=[
            {
                "candidate_title": "Incident Timeline Explorer",
                "adequacy_class": "cited_with_direct_scope",
            },
            {
                "candidate_title": "Lineage Blast Radius Explorer",
                "adequacy_class": "cited_with_direct_scope",
            },
        ],
        encoder=FakeEncoder(),
        unique_angle_threshold=0.78,
        case_id="cloud_incident_001",
    )

    assert comparison.case_id == "cloud_incident_001"
    assert comparison.unique_angle_count == 1
    assert comparison.unique_openai_titles == [
        "Lineage Blast Radius Explorer"
    ]
    assert comparison.set_similarity_score is not None
    assert len(comparison.pairwise_similarity) == 2
    assert comparison.openai_grounding_classes == [
        {
            "candidate_title": "Incident Timeline Explorer",
            "adequacy_class": "cited_with_direct_scope",
        },
        {
            "candidate_title": "Lineage Blast Radius Explorer",
            "adequacy_class": "cited_with_direct_scope",
        },
    ]


def test_comparison_keeps_enrichment_and_manual_review_fields_neutral():
    comparison = build_shadow_vs_deterministic_comparison(
        user_goal="Build a data reliability project.",
        constraints={},
        deterministic_candidates=[
            {
                "project_title": "Pipeline Monitor",
                "idea_angle": "Monitor quality checks.",
                "mvp_scope": ["Load records.", "Run checks."],
            }
        ],
        openai_candidates=[
            make_candidate(
                "Lineage Explorer",
                "Trace downstream impact.",
            )
        ],
        deterministic_enriched_ideas=[
            {
                "project_title": "Pipeline Monitor",
                "feasibility_analysis": {
                    "build_profile": {
                        "tier": "Quick Win",
                        "difficulty": "Easy",
                    }
                },
            }
        ],
        openai_enriched_ideas=[
            {
                "project_title": "Lineage Explorer",
                "feasibility_analysis": {
                    "build_profile": {
                        "tier": "Portfolio Build",
                        "difficulty": "Medium",
                    }
                },
                "planner_provenance": {
                    "planning_source": "openai_repaired",
                },
            }
        ],
    )

    payload = comparison.to_dict()

    assert payload["manual_preference"] is None
    assert payload["manual_reviewer_notes"] is None
    assert payload["deterministic_enrichment"][0]["difficulty"] == "Easy"
    assert payload["openai_enrichment"][0]["planner_provenance"] == {
        "planning_source": "openai_repaired",
    }
    assert payload["deterministic_grounding_classes"][0][
        "adequacy_class"
    ] == "not_assessed"
    assert payload["set_similarity_score"] is None
