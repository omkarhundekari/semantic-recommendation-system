from planning.candidate_models import CandidateDirection
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_goal_relevance import EmbeddingVector
from planning.shadow_comparison_enrichment import (
    build_shadow_comparison_enrichment,
)


class FakeEncoder:
    def encode_text(self, text):
        text = text.lower()

        if "lineage" in text or "blast radius" in text:
            return EmbeddingVector((0.0, 1.0))

        return EmbeddingVector((1.0, 0.0))


def make_brief():
    return EvidenceBrief(
        query="Build a data quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Research",
                excerpt="Data quality needs reliable validation.",
                support_scope="direct",
            )
        ],
    )


def make_candidate():
    return CandidateDirection(
        title="Lineage Blast Radius Explorer",
        problem_statement=(
            "Data engineers need to understand downstream incident impact."
        ),
        target_user="data engineers",
        core_workflow=[
            "Load incident and lineage records.",
            "Trace downstream blast radius.",
        ],
        mvp_scope=[
            "Load sample lineage edges.",
            "Compute affected downstream assets.",
            "Show an impact report.",
        ],
        success_metrics=["Faster impact review."],
        evidence_relationship="Uses retained data-quality evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def make_legacy_idea():
    return {
        "project_title": "Pipeline Quality Monitor",
        "idea_angle": "Monitor data quality checks.",
        "detected_domain": "data_engineering",
        "mvp_scope": [
            "Load sample pipeline records.",
            "Run validation checks.",
            "Show quality results.",
        ],
        "advanced_extensions": [],
        "suggested_tech_stack": ["Python", "FastAPI"],
        "target_roles": ["Data Engineer"],
        "research_motivation": "Uses retained data-quality evidence.",
        "evidence_title": "Data Quality Research",
        "evidence_source_type": "research_paper",
    }


def test_builds_complete_enrichment_and_comparison_payload():
    result = build_shadow_comparison_enrichment(
        user_goal="Build a data quality project.",
        constraints={
            "time_available": "3 weeks",
            "target_roles": ["Data Engineer"],
            "preferred_stack": [],
        },
        detected_domain="data_engineering",
        brief=make_brief(),
        legacy_ideas=[make_legacy_idea()],
        selected_candidates=[make_candidate().to_dict()],
        grounding_adequacy=[
            {
                "candidate_title": "Lineage Blast Radius Explorer",
                "adequacy_class": "cited_with_direct_scope",
            }
        ],
        promotion_eligibility={
            "candidate_assessments": [
                {
                    "candidate_title": "Lineage Blast Radius Explorer",
                    "eligible_for_product_promotion": True,
                    "signals": {
                        "has_flagged_duplicate_pair": False,
                    },
                }
            ]
        },
        generation_metadata={"prompt_version": "v1"},
        comparison_encoder=FakeEncoder(),
    )

    assert result["legacy_raw_ideas"][0]["project_title"] == (
        "Pipeline Quality Monitor"
    )
    assert result["legacy_enrichment"]["ideas"][0][
        "project_title"
    ] == "Pipeline Quality Monitor"

    shadow_idea = result["shadow_enrichment"]["ideas"][0]
    assert shadow_idea["planner_provenance"]["planning_source"] == (
        "openai"
    )
    assert shadow_idea["planner_provenance"]["promotion_eligible"] is True

    comparison = result["comparison"]
    assert comparison["unique_angle_count"] == 1
    assert comparison["openai_grounding_classes"][0][
        "adequacy_class"
    ] == "cited_with_direct_scope"


def test_handles_prompt_ready_artifacts_without_shadow_candidates():
    result = build_shadow_comparison_enrichment(
        user_goal="Build a data quality project.",
        constraints={},
        detected_domain="data_engineering",
        brief=make_brief(),
        legacy_ideas=[make_legacy_idea()],
        selected_candidates=[],
        grounding_adequacy=[],
        promotion_eligibility={},
        generation_metadata={"prompt_version": "v1"},
    )

    assert result["shadow_raw_candidates"] == []
    assert result["shadow_enrichment"]["ideas"] == []
    assert result["comparison"]["unique_angle_count"] == 0
