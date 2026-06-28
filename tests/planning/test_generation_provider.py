from planning.candidate_generation_service import (
    generate_validated_candidates,
)
from planning.candidate_models import CandidateGenerationRequest
from planning.mock_generation_provider import (
    MockCandidateGenerationProvider,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def valid_response():
    return {
        "candidates": [
            {
                "title": "Incident Correlation Workbench",
                "problem_statement": "Incident evidence is fragmented.",
                "target_user": "Platform engineers",
                "core_workflow": [
                    "Ingest service events.",
                    "Correlate related signals.",
                ],
                "mvp_scope": [
                    "Load sample events.",
                    "Correlate related records.",
                    "Render an investigation timeline.",
                ],
                "success_metrics": [
                    "Time to identify related events.",
                ],
                "evidence_relationship": (
                    "Uses the event-correlation workflow from the evidence brief."
                ),
                "source_ids": ["paper-1"],
                "assumptions": ["Use synthetic incident data."],
                "suggested_stack": ["Python", "FastAPI"],
            }
        ]
    }


def make_brief():
    return EvidenceBrief(
        query="Build a service investigation tool.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation for Incident Response",
                excerpt=(
                    "Event correlation improves incident investigation "
                    "workflows."
                ),
            )
        ],
    )


def test_mock_provider_runs_full_prompt_parse_validate_flow():
    provider = MockCandidateGenerationProvider(
        response=valid_response()
    )
    request = CandidateGenerationRequest(
        user_goal="Build a platform-engineering project.",
        time_available="3 weeks",
        target_roles=["Platform Engineer"],
    )

    outcome = generate_validated_candidates(
        brief=make_brief(),
        request=request,
        provider=provider,
    )

    assert outcome.provider_called is True
    assert len(provider.prompts) == 1
    assert len(outcome.candidates) == 1
    assert len(outcome.valid_candidates) == 1
    assert outcome.validations[0].is_valid is True


def test_invalid_provider_source_is_filtered_by_validation():
    response = valid_response()
    response["candidates"][0]["source_ids"] = ["invented-source"]

    outcome = generate_validated_candidates(
        brief=make_brief(),
        request=CandidateGenerationRequest(
            user_goal="Build a platform-engineering project."
        ),
        provider=MockCandidateGenerationProvider(response=response),
    )

    assert outcome.valid_candidates == []
    assert outcome.validations[0].is_valid is False
