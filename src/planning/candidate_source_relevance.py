import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from planning.candidate_models import CandidateDirection
from planning.planner_models import EvidenceBrief, EvidenceSource


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "into", "is", "it", "of", "on", "or", "that", "the", "to",
    "with", "which", "who", "will", "can", "need", "needs", "teams",
    "team", "tool", "tools", "system", "systems", "project", "data",
    "show", "load", "use", "uses", "using", "build", "buildable",
    "engineers", "engineering", "workflows", "workflow",
}


def _content_terms(text: str) -> List[str]:
    return sorted(
        {
            token
            for token in _TOKEN_PATTERN.findall(text.lower())
            if len(token) > 3 and token not in _STOPWORDS
        }
    )


def _candidate_text(candidate: CandidateDirection) -> str:
    return " ".join(
        part
        for part in [
            candidate.title,
            candidate.problem_statement,
            candidate.target_user,
            " ".join(candidate.core_workflow),
        ]
        if part
    )


def _source_text(source: EvidenceSource) -> str:
    return " ".join(
        part
        for part in [source.title, source.excerpt]
        if part
    )


@dataclass(frozen=True)
class CandidateSourceRelevanceTrace:
    candidate_title: str
    source_id: str
    source_type: str
    support_scope: str
    candidate_source_shared_terms: List[str]
    goal_source_shared_terms: List[str]
    relevance_status: str
    relevance_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def assess_candidate_source_relevance(
    candidate: CandidateDirection,
    brief: EvidenceBrief,
    user_goal: str,
) -> List[CandidateSourceRelevanceTrace]:
    sources_by_id = {
        source.source_id: source
        for source in brief.sources
    }

    candidate_terms = set(_content_terms(_candidate_text(candidate)))
    goal_terms = set(_content_terms(user_goal))
    traces: List[CandidateSourceRelevanceTrace] = []

    for source_id in candidate.source_ids:
        source = sources_by_id.get(source_id)

        if source is None:
            traces.append(
                CandidateSourceRelevanceTrace(
                    candidate_title=candidate.title,
                    source_id=source_id,
                    source_type="unknown",
                    support_scope="unknown",
                    candidate_source_shared_terms=[],
                    goal_source_shared_terms=[],
                    relevance_status="invalid_source_id",
                    relevance_reason=(
                        "The cited source ID does not exist in the "
                        "evidence brief."
                    ),
                )
            )
            continue

        source_terms = set(_content_terms(_source_text(source)))
        candidate_shared = sorted(candidate_terms.intersection(source_terms))
        goal_shared = sorted(goal_terms.intersection(source_terms))

        if source.support_scope == "adjacent_planning":
            status = "adjacent_context_only"
            reason = (
                "The cited source is retained only as adjacent planning "
                "context and should not be treated as core grounding."
            )
        elif candidate_shared:
            status = "lexically_supported"
            reason = (
                "Candidate and source share content terms: "
                + ", ".join(candidate_shared[:5])
                + "."
            )
        else:
            status = "possible_mismatch"
            reason = (
                "No non-generic content terms are shared between the "
                "candidate and cited source."
            )

        traces.append(
            CandidateSourceRelevanceTrace(
                candidate_title=candidate.title,
                source_id=source.source_id,
                source_type=source.source_type,
                support_scope=source.support_scope,
                candidate_source_shared_terms=candidate_shared,
                goal_source_shared_terms=goal_shared,
                relevance_status=status,
                relevance_reason=reason,
            )
        )

    return traces


def assess_candidate_set_source_relevance(
    candidates: Sequence[CandidateDirection],
    brief: EvidenceBrief,
    user_goal: str,
) -> List[CandidateSourceRelevanceTrace]:
    traces: List[CandidateSourceRelevanceTrace] = []

    for candidate in candidates:
        traces.extend(
            assess_candidate_source_relevance(
                candidate=candidate,
                brief=brief,
                user_goal=user_goal,
            )
        )

    return traces
