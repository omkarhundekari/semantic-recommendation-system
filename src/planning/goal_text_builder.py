from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)


def build_goal_text(
    request: CandidateGenerationRequest,
) -> str:
    parts = [request.user_goal.strip()]

    if request.target_roles:
        parts.append(
            "Target roles: "
            + ", ".join(request.target_roles)
            + "."
        )

    return " ".join(part for part in parts if part)


def build_candidate_text(
    candidate: CandidateDirection,
) -> str:
    parts = [
        candidate.title.strip().rstrip("."),
        candidate.problem_statement.strip().rstrip("."),
        candidate.target_user.strip().rstrip("."),
    ]

    return ". ".join(part for part in parts if part)
