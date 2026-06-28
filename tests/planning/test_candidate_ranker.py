from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.candidate_ranker import (
    rank_candidates,
    select_diverse_candidates,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def make_brief():
    return EvidenceBrief(
        query="Build a service incident investigation tool.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation for Incident Response",
                excerpt="Correlate service events during incidents.",
            ),
            EvidenceSource(
                source_id="repo-1",
                source_type="github_repository",
                title="Incident Timeline Toolkit",
                excerpt="Build timelines from service health signals.",
            ),
        ],
    )


def make_candidate(
    title,
    source_ids,
    workflow=None,
    mvp_scope=None,
    stack=None,
):
    return CandidateDirection(
        title=title,
        problem_statement="Operational evidence is fragmented.",
        target_user="Platform engineers",
        core_workflow=workflow or [
            "Ingest operational events.",
            "Correlate related signals.",
        ],
        mvp_scope=mvp_scope or [
            "Load sample records.",
            "Correlate events.",
            "Show an investigation view.",
        ],
        success_metrics=["Time to identify related events."],
        evidence_relationship="Grounded in evidence-supported incident workflows.",
        source_ids=source_ids,
        suggested_stack=stack or ["Python", "FastAPI"],
    )


def test_ranker_prefers_supported_feasible_candidate():
    strong = make_candidate(
        "Incident Correlation Workbench",
        ["paper-1", "repo-1"],
    )
    weak = make_candidate(
        "Large Operations Intelligence Suite",
        [],
        mvp_scope=[
            "Ingest events.",
            "Build correlation.",
            "Build dashboards.",
            "Add alerting.",
            "Add analytics.",
            "Add deployment.",
            "Add integrations.",
            "Add multi-tenant support.",
        ],
        stack=[
            "Python",
            "FastAPI",
            "React",
            "Docker",
            "Kubernetes",
            "PostgreSQL",
            "Redis",
            "Kafka",
        ],
    )

    ranked = rank_candidates(
        candidates=[weak, strong],
        brief=make_brief(),
        request=CandidateGenerationRequest(
            user_goal="Build a platform engineering project.",
            time_available="3 weeks",
            target_roles=["Platform Engineer"],
            preferred_stack=["Python", "FastAPI"],
        ),
    )

    assert ranked[0].candidate.title == "Incident Correlation Workbench"
    assert ranked[0].score > ranked[1].score


def test_diversity_selector_skips_near_duplicate_direction():
    first = make_candidate(
        "Incident Correlation Workbench",
        ["paper-1"],
    )
    duplicate = make_candidate(
        "Incident Event Correlation Dashboard",
        ["paper-1"],
    )
    distinct = make_candidate(
        "Deployment Change Investigation Timeline",
        ["repo-1"],
        workflow=[
            "Ingest deployment changes.",
            "Compare health signals after releases.",
        ],
        mvp_scope=[
            "Load deployment records.",
            "Compare deployment and health events.",
            "Show release investigation timeline.",
        ],
    )

    ranked = rank_candidates(
        candidates=[first, duplicate, distinct],
        brief=make_brief(),
        request=CandidateGenerationRequest(
            user_goal="Build a platform engineering project."
        ),
    )

    selected = select_diverse_candidates(
        ranked,
        max_candidates=2,
    )

    selected_titles = [item.candidate.title for item in selected]

    assert "Incident Correlation Workbench" in selected_titles
    assert "Deployment Change Investigation Timeline" in selected_titles
    assert "Incident Event Correlation Dashboard" not in selected_titles
