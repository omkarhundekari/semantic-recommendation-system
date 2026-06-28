import json

from planning.candidate_models import CandidateGenerationRequest
from planning.candidate_prompt import build_candidate_generation_prompt
from planning.planner_models import EvidenceBrief, EvidenceSource


def test_prompt_contains_only_structured_brief_and_generation_rules():
    brief = EvidenceBrief(
        query="Build an incident investigation tool.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation for Incident Response",
                excerpt="Event correlation can improve incident investigation.",
            )
        ],
    )
    request = CandidateGenerationRequest(
        user_goal="Build a platform-engineering project.",
        time_available="3 weeks",
        target_roles=["Platform Engineer"],
    )

    payload = json.loads(
        build_candidate_generation_prompt(
            brief=brief,
            request=request,
        )
    )

    assert payload["evidence_brief"]["sources"][0]["source_id"] == "paper-1"
    assert "Do not invent papers" in " ".join(payload["rules"])
    assert payload["required_schema"]["candidates"]
