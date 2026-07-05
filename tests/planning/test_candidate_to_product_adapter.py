from planning.candidate_models import CandidateDirection
from planning.candidate_to_product_adapter import (
    adapt_candidate_to_product_idea,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def make_candidate():
    return CandidateDirection(
        title="Incident Correlation Workbench",
        problem_statement=(
            "Platform engineers need a faster way to connect deployments, "
            "health signals, and incident events."
        ),
        target_user="platform engineers",
        core_workflow=[
            "Load deployment and incident events.",
            "Correlate related operational signals.",
        ],
        mvp_scope=[
            "Load representative incident records.",
            "Build a deployment-to-incident timeline.",
            "Show correlated events in an investigation view.",
        ],
        success_metrics=[
            "Reduce time required to identify related events.",
        ],
        evidence_relationship=(
            "Uses evidence-supported incident investigation patterns."
        ),
        source_ids=["repo-1", "paper-1"],
        assumptions=[
            "The first version uses synthetic operational data."
        ],
        suggested_stack=["Python", "FastAPI", "React"],
    )


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
            ),
            EvidenceSource(
                source_id="repo-1",
                source_type="github_repository",
                title="Deployment Timeline Toolkit",
                excerpt="Build timelines from deployment signals.",
                url="https://example.com/repo",
                support_scope="adjacent_planning",
            ),
        ],
    )


def test_adapts_candidate_into_legacy_product_idea_contract():
    idea = adapt_candidate_to_product_idea(
        candidate=make_candidate(),
        brief=make_brief(),
        detected_domain="cloud_platform",
        target_roles=["Platform Engineer"],
    )

    assert idea["project_title"] == "Incident Correlation Workbench"
    assert idea["detected_domain"] == "cloud_platform"
    assert idea["mvp_scope"] == [
        "Load representative incident records.",
        "Build a deployment-to-incident timeline.",
        "Show correlated events in an investigation view.",
    ]
    assert idea["suggested_tech_stack"] == [
        "Python",
        "FastAPI",
        "React",
    ]
    assert idea["target_roles"] == ["Platform Engineer"]

    assert idea["evidence_title"] == (
        "Event Correlation for Incident Response"
    )
    assert idea["evidence_source_type"] == "research_paper"
    assert idea["evidence_url"] == "https://example.com/paper"
    assert idea["research_category"] == "cs.SE"

    assert idea["planner_candidate_source_ids"] == [
        "repo-1",
        "paper-1",
    ]
    assert len(idea["source_contributions"]) == 2
    assert idea["source_contributions"][0]["source_id"] == "repo-1"


def test_prefers_direct_source_over_earlier_adjacent_source():
    idea = adapt_candidate_to_product_idea(
        candidate=make_candidate(),
        brief=make_brief(),
        detected_domain="cloud_platform",
    )

    assert idea["evidence_title"] == (
        "Event Correlation for Incident Response"
    )


def test_uses_first_known_source_when_no_direct_source_exists():
    candidate = make_candidate()
    brief = EvidenceBrief(
        query="Build a project.",
        sources=[
            EvidenceSource(
                source_id="repo-1",
                source_type="github_repository",
                title="Operations Toolkit",
                excerpt="Operational workflow reference.",
                support_scope="adjacent_planning",
            )
        ],
    )

    idea = adapt_candidate_to_product_idea(
        candidate=candidate,
        brief=brief,
        detected_domain="cloud_platform",
    )

    assert idea["evidence_title"] == "Operations Toolkit"
    assert idea["evidence_source_type"] == "github_repository"


def test_adapter_produces_fields_needed_by_existing_verifier():
    idea = adapt_candidate_to_product_idea(
        candidate=make_candidate(),
        brief=make_brief(),
        detected_domain="cloud_platform",
        target_roles=["Platform Engineer"],
    )

    required_fields = {
        "project_title",
        "idea_angle",
        "mvp_scope",
        "suggested_tech_stack",
        "target_roles",
        "research_motivation",
        "evidence_title",
        "evidence_source_type",
    }

    assert required_fields.issubset(idea)
