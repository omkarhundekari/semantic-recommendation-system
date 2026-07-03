from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.goal_text_builder import (
    build_candidate_text,
    build_goal_text,
)


def test_build_goal_text_includes_target_roles_when_present():
    request = CandidateGenerationRequest(
        user_goal="Build an incident investigation project.",
        target_roles=["Platform Engineer", "SRE"],
    )

    assert build_goal_text(request) == (
        "Build an incident investigation project. "
        "Target roles: Platform Engineer, SRE."
    )


def test_build_goal_text_uses_only_goal_when_roles_are_missing():
    request = CandidateGenerationRequest(
        user_goal="Build an incident investigation project.",
    )

    assert build_goal_text(request) == (
        "Build an incident investigation project."
    )


def test_build_candidate_text_uses_shared_semantic_fields_only():
    candidate = CandidateDirection(
        title="Incident Timeline.",
        problem_statement="Connect operational signals.",
        target_user="Platform engineers.",
        core_workflow=[],
        mvp_scope=[],
        success_metrics=[],
        evidence_relationship="",
        suggested_stack=["Python", "FastAPI"],
    )

    assert build_candidate_text(candidate) == (
        "Incident Timeline. Connect operational signals. "
        "Platform engineers"
    )
