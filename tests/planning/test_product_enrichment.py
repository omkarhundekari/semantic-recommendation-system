from copy import deepcopy

from planning.candidate_models import CandidateDirection
from planning.candidate_provenance import CandidateProvenance
from planning.candidate_to_product_adapter import (
    adapt_candidate_to_product_idea,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.product_enrichment import enrich_product_ideas


def make_brief():
    return EvidenceBrief(
        query="Build a cloud incident investigation project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation for Incident Response",
                excerpt="Correlate operational events during incidents.",
                category="cs.SE",
                url="https://example.com/paper",
                support_scope="direct",
            )
        ],
    )


def make_candidate(title, workflow_suffix):
    return CandidateDirection(
        title=title,
        problem_statement=(
            "Platform engineers need a clearer way to investigate "
            "operational failures."
        ),
        target_user="platform engineers",
        core_workflow=[
            "Load representative operational events.",
            workflow_suffix,
        ],
        mvp_scope=[
            "Load representative incident records.",
            workflow_suffix,
            "Show an investigation summary with evidence links.",
        ],
        success_metrics=[
            "Reduce time required to investigate an incident.",
        ],
        evidence_relationship=(
            "Uses direct evidence about operational event correlation."
        ),
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI", "React"],
    )


def make_ideas():
    brief = make_brief()
    provenance = CandidateProvenance(
        planning_source="openai_repaired",
        prompt_version="v1",
        generation_attempt=3,
        replacement_angle=(
            "Use lineage-aware impact mapping instead of a duplicate "
            "schema-drift workflow."
        ),
        rejected_alternatives=2,
        grounding_adequacy="cited_with_direct_scope",
        diversity_check_passed=True,
        promotion_eligible=True,
    )

    first = adapt_candidate_to_product_idea(
        candidate=make_candidate(
            "Incident Timeline Correlator",
            "Build a deployment-to-incident timeline.",
        ),
        brief=brief,
        detected_domain="cloud",
        target_roles=["Platform Engineer"],
    )

    second = adapt_candidate_to_product_idea(
        candidate=make_candidate(
            "Incident Blast Radius Explorer",
            "Trace downstream systems affected by an incident.",
        ),
        brief=brief,
        detected_domain="cloud",
        target_roles=["Platform Engineer"],
        planner_provenance=provenance,
    )

    return [first, second]


def test_enrichment_is_deterministic_for_same_ordered_candidate_set():
    ideas = make_ideas()
    constraints = {
        "target_roles": ["Platform Engineer"],
        "preferred_stack": [],
        "time_available": "3 weeks",
    }

    first = enrich_product_ideas(
        ideas=ideas,
        constraints=constraints,
    )
    second = enrich_product_ideas(
        ideas=ideas,
        constraints=constraints,
    )

    assert first.to_dict() == second.to_dict()


def test_enrichment_does_not_mutate_caller_owned_ideas():
    ideas = make_ideas()
    original = deepcopy(ideas)

    enrich_product_ideas(
        ideas=ideas,
        constraints={
            "target_roles": ["Platform Engineer"],
            "preferred_stack": [],
            "time_available": "3 weeks",
        },
    )

    assert ideas == original


def test_enrichment_preserves_adapter_provenance():
    result = enrich_product_ideas(
        ideas=make_ideas(),
        constraints={
            "target_roles": ["Platform Engineer"],
            "preferred_stack": [],
            "time_available": "3 weeks",
        },
    )

    provenance = result.ideas[1]["planner_provenance"]

    assert provenance["planning_source"] == "openai_repaired"
    assert provenance["generation_attempt"] == 3
    assert provenance["rejected_alternatives"] == 2


def test_enrichment_assigns_ladder_profiles_in_candidate_order():
    result = enrich_product_ideas(
        ideas=make_ideas(),
        constraints={
            "target_roles": ["Platform Engineer"],
            "preferred_stack": [],
            "time_available": "3 weeks",
        },
    )

    profiles = [
        idea["feasibility_analysis"]["build_profile"]["difficulty"]
        for idea in result.ideas
    ]

    assert profiles == ["Easy", "Medium"]
