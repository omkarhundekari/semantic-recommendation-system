import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from planning.candidate_models import CandidateDirection


CandidateLike = Union[CandidateDirection, Mapping[str, Any]]


def _canonical_constraints(
    constraints: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return dict(constraints or {})


def build_query_fingerprint(
    user_goal: str,
    constraints: Optional[Dict[str, Any]] = None,
) -> str:
    payload = {
        "query": " ".join(str(user_goal).lower().split()),
        "constraints": _canonical_constraints(constraints),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()[:16]


def _candidate_value(
    candidate: CandidateLike,
    key: str,
    default: Any = None,
) -> Any:
    if isinstance(candidate, CandidateDirection):
        return getattr(candidate, key, default)

    return candidate.get(key, default)


def _candidate_title(candidate: CandidateLike) -> str:
    return str(
        _candidate_value(
            candidate,
            "title",
            _candidate_value(candidate, "project_title", ""),
        )
    ).strip()


def _as_text_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def build_comparison_text(candidate: CandidateLike) -> str:
    title = _candidate_title(candidate)
    problem_statement = _candidate_value(
        candidate,
        "problem_statement",
        _candidate_value(candidate, "idea_angle", ""),
    )
    target_user = _candidate_value(candidate, "target_user", "")
    workflow = _as_text_list(
        _candidate_value(
            candidate,
            "core_workflow",
            _candidate_value(candidate, "mvp_scope", []),
        )
    )
    mvp_scope = _as_text_list(
        _candidate_value(candidate, "mvp_scope", [])
    )

    return " ".join(
        part
        for part in [
            title,
            str(problem_statement).strip(),
            str(target_user).strip(),
            " ".join(workflow),
            " ".join(mvp_scope),
        ]
        if part
    )


def _safe_cosine(left: Any, right: Any) -> float:
    return round(float(left.cosine_similarity(right)), 4)


def _profile_summary(idea: Mapping[str, Any]) -> Dict[str, Any]:
    feasibility = idea.get("feasibility_analysis", {})
    profile = (
        feasibility.get("build_profile", {})
        if isinstance(feasibility, dict)
        else {}
    )

    verification = idea.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}

    return {
        "title": str(idea.get("project_title", "")).strip(),
        "scope": profile.get("scope"),
        "estimated_effort": profile.get("estimated_effort"),
        "portfolio_tier": profile.get("tier"),
        "difficulty": profile.get("difficulty"),
        "verification_status": verification.get("status"),
        "verification_score": verification.get("score"),
        "verification_max_score": verification.get("max_score"),
        "planner_provenance": idea.get("planner_provenance"),
    }


def _grounding_by_title(
    traces: Optional[Sequence[Mapping[str, Any]]],
) -> Dict[str, str]:
    result: Dict[str, str] = {}

    for trace in traces or []:
        title = str(trace.get("candidate_title", "")).strip()
        adequacy = str(trace.get("adequacy_class", "")).strip()

        if title and adequacy:
            result[title] = adequacy

    return result


@dataclass(frozen=True)
class ShadowVsDeterministicComparison:
    schema_version: str
    case_id: Optional[str]
    user_goal: str
    query_fingerprint: str

    deterministic_candidates: List[Dict[str, Any]]
    openai_candidates: List[Dict[str, Any]]

    deterministic_grounding_classes: List[Dict[str, str]]
    openai_grounding_classes: List[Dict[str, str]]

    deterministic_enrichment: List[Dict[str, Any]]
    openai_enrichment: List[Dict[str, Any]]

    set_similarity_score: Optional[float]
    unique_angle_count: int
    unique_openai_titles: List[str]
    pairwise_similarity: List[Dict[str, Any]]

    manual_preference: Optional[str] = None
    manual_preference_reason: Optional[str] = None
    manual_reviewer_notes: Optional[str] = None

    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_shadow_vs_deterministic_comparison(
    user_goal: str,
    constraints: Optional[Dict[str, Any]],
    deterministic_candidates: Sequence[CandidateLike],
    openai_candidates: Sequence[CandidateLike],
    deterministic_enriched_ideas: Optional[
        Sequence[Mapping[str, Any]]
    ] = None,
    openai_enriched_ideas: Optional[
        Sequence[Mapping[str, Any]]
    ] = None,
    openai_grounding_adequacy: Optional[
        Sequence[Mapping[str, Any]]
    ] = None,
    encoder: Optional[Any] = None,
    unique_angle_threshold: float = 0.78,
    case_id: Optional[str] = None,
) -> ShadowVsDeterministicComparison:
    """
    Compare deterministic and shadow-LLM candidate sets without deciding which
    set is better. Semantic difference is recorded as a review signal only.

    Deterministic grounding remains "not_assessed" until its own grounding
    contract is explicitly implemented. This avoids presenting incomparable
    signals as though they were equivalent.
    """
    deterministic_list = list(deterministic_candidates)
    openai_list = list(openai_candidates)

    deterministic_titles = [
        _candidate_title(candidate)
        for candidate in deterministic_list
    ]
    openai_titles = [
        _candidate_title(candidate)
        for candidate in openai_list
    ]

    openai_grounding = _grounding_by_title(
        openai_grounding_adequacy
    )

    pairwise_similarity: List[Dict[str, Any]] = []
    unique_openai_titles: List[str] = []
    set_similarity_score: Optional[float] = None

    if encoder is not None and deterministic_list and openai_list:
        deterministic_embeddings = [
            encoder.encode_text(build_comparison_text(candidate))
            for candidate in deterministic_list
        ]
        openai_embeddings = [
            encoder.encode_text(build_comparison_text(candidate))
            for candidate in openai_list
        ]

        all_scores = []
        highest_match_by_openai_title: Dict[str, float] = {}

        for openai_candidate, openai_embedding in zip(
            openai_list,
            openai_embeddings,
        ):
            openai_title = _candidate_title(openai_candidate)
            candidate_scores = []

            for deterministic_candidate, deterministic_embedding in zip(
                deterministic_list,
                deterministic_embeddings,
            ):
                score = _safe_cosine(
                    openai_embedding,
                    deterministic_embedding,
                )
                candidate_scores.append(score)
                all_scores.append(score)

                pairwise_similarity.append(
                    {
                        "openai_title": openai_title,
                        "deterministic_title": _candidate_title(
                            deterministic_candidate
                        ),
                        "raw_cosine": score,
                    }
                )

            highest_match_by_openai_title[openai_title] = max(
                candidate_scores,
                default=0.0,
            )

        unique_openai_titles = [
            title
            for title in openai_titles
            if highest_match_by_openai_title.get(title, 0.0)
            < unique_angle_threshold
        ]

        set_similarity_score = round(
            sum(all_scores) / len(all_scores),
            4,
        )

    deterministic_grounding_classes = [
        {
            "candidate_title": title,
            "adequacy_class": "not_assessed",
        }
        for title in deterministic_titles
        if title
    ]

    openai_grounding_classes = [
        {
            "candidate_title": title,
            "adequacy_class": openai_grounding.get(
                title,
                "not_assessed",
            ),
        }
        for title in openai_titles
        if title
    ]

    notes = [
        (
            "Cross-set semantic similarity is a difference signal, not a "
            "quality score."
        ),
        (
            "Portfolio tiers are preserved for review but are assigned by "
            "candidate order and must not be interpreted as quality labels."
        ),
        (
            "Deterministic grounding is not assessed by this contract yet; "
            "only shadow grounding traces are currently comparable."
        ),
    ]

    return ShadowVsDeterministicComparison(
        schema_version="1.0",
        case_id=case_id,
        user_goal=user_goal,
        query_fingerprint=build_query_fingerprint(
            user_goal=user_goal,
            constraints=constraints,
        ),
        deterministic_candidates=[
            {
                "title": _candidate_title(candidate),
                "comparison_text": build_comparison_text(candidate),
            }
            for candidate in deterministic_list
        ],
        openai_candidates=[
            {
                "title": _candidate_title(candidate),
                "comparison_text": build_comparison_text(candidate),
            }
            for candidate in openai_list
        ],
        deterministic_grounding_classes=(
            deterministic_grounding_classes
        ),
        openai_grounding_classes=openai_grounding_classes,
        deterministic_enrichment=[
            _profile_summary(idea)
            for idea in (deterministic_enriched_ideas or [])
        ],
        openai_enrichment=[
            _profile_summary(idea)
            for idea in (openai_enriched_ideas or [])
        ],
        set_similarity_score=set_similarity_score,
        unique_angle_count=len(unique_openai_titles),
        unique_openai_titles=unique_openai_titles,
        pairwise_similarity=pairwise_similarity,
        notes=notes,
    )
