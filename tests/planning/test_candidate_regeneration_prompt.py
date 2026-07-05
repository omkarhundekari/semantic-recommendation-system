import json

from planning.candidate_models import CandidateGenerationRequest
from planning.candidate_regeneration_prompt import (
    REGENERATION_PROMPT_VERSION,
    build_candidate_regeneration_payload,
    build_candidate_regeneration_prompt,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)


def make_brief():
    return EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Monitoring Research",
                excerpt="Data validation improves pipeline reliability.",
                support_scope="direct",
            )
        ],
    )


def make_request():
    return CandidateGenerationRequest(
        user_goal="Build a data pipeline quality project.",
        skill_level="intermediate",
        time_available="3 weeks",
        target_roles=["Data Engineer"],
        preferred_stack=["Python", "FastAPI"],
    )


def make_directive():
    return DiversificationRepairDirective(
        replace_candidate_title="Pipeline Failure Triage",
        retain_candidate_titles=["Pipeline Monitor"],
        highest_pair_similarity=0.7915,
        reason="Candidate is too similar to a higher-ranked direction.",
        regeneration_brief={
            "preserve_user_goal": True,
            "preserve_evidence_constraints": True,
            "must_differ_from_titles": ["Pipeline Monitor"],
            "avoid_retained_workflow": [
                "Run validation checks.",
                "Show quality alerts.",
            ],
            "avoid_retained_mvp_scope": [
                "Load pipeline records.",
                "Run validation checks.",
                "Show alert results.",
            ],
            "requirement": (
                "Use a materially distinct technical workflow."
            ),
        },
    )


def test_builds_one_candidate_regeneration_payload():
    payload = build_candidate_regeneration_payload(
        brief=make_brief(),
        request=make_request(),
        directive=make_directive(),
    )

    assert payload["task"].startswith("Generate exactly one")
    assert payload["user_request"]["time_available"] == "3 weeks"
    assert payload["evidence_brief"]["sources"][0]["source_id"] == (
        "paper-1"
    )

    directive = payload["repair_directive"]

    assert directive["replace_candidate_title"] == (
        "Pipeline Failure Triage"
    )
    assert directive["retain_candidate_titles"] == ["Pipeline Monitor"]
    assert directive["highest_pair_similarity"] == 0.7915
    assert directive["regeneration_brief"][
        "must_differ_from_titles"
    ] == ["Pipeline Monitor"]

    assert set(payload["required_schema"]["candidate"]) == {
        "title",
        "problem_statement",
        "target_user",
        "core_workflow",
        "mvp_scope",
        "success_metrics",
        "evidence_relationship",
        "source_ids",
        "assumptions",
        "suggested_stack",
    }


def test_serializes_regeneration_payload_as_valid_json():
    prompt = build_candidate_regeneration_prompt(
        brief=make_brief(),
        request=make_request(),
        directive=make_directive(),
    )

    parsed = json.loads(prompt)

    assert REGENERATION_PROMPT_VERSION == "v1"
    assert parsed["repair_directive"]["replace_candidate_title"] == (
        "Pipeline Failure Triage"
    )
    assert (
        "Do not repeat any surviving candidate's primary workflow"
        in parsed["rules"][3]
    )


def test_includes_all_surviving_candidate_exclusions():
    from planning.candidate_models import CandidateDirection

    schema_guard = CandidateDirection(
        title="Schema Drift Detection and Data Contract Guard",
        problem_statement="Teams need contract-aware schema review.",
        target_user="Data engineers",
        core_workflow=[
            "Compare observed schemas with declared contracts.",
            "Explain changed fields and downstream impact.",
        ],
        mvp_scope=[
            "Load schema snapshots.",
            "Compare contract versions.",
            "Show drift findings.",
        ],
        success_metrics=["Breaking changes are visible."],
        evidence_relationship="Uses retained evidence.",
        source_ids=["paper-1"],
    )

    payload = build_candidate_regeneration_payload(
        brief=make_brief(),
        request=make_request(),
        directive=make_directive(),
        surviving_candidates=[schema_guard],
    )

    exclusions = payload["surviving_candidates_to_avoid"]

    assert exclusions == [
        {
            "title": "Schema Drift Detection and Data Contract Guard",
            "core_workflow": [
                "Compare observed schemas with declared contracts.",
                "Explain changed fields and downstream impact.",
            ],
            "mvp_scope": [
                "Load schema snapshots.",
                "Compare contract versions.",
                "Show drift findings.",
            ],
        }
    ]
    assert "any surviving candidate" in payload["rules"][3]
