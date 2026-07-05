from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ShadowFixtureCase:
    case_id: str
    user_goal: str
    constraints: Dict[str, object]
    coverage_tags: Tuple[str, ...]
    evaluation_hypotheses: Tuple[str, ...]
    reviewer_focus: str
    notes: str = ""

    def validate(self) -> None:
        if not self.case_id.strip():
            raise ValueError("Fixture case_id must be non-empty.")

        if not self.user_goal.strip():
            raise ValueError(
                f"Fixture {self.case_id} must include a user goal."
            )

        if not self.coverage_tags:
            raise ValueError(
                f"Fixture {self.case_id} must include coverage tags."
            )

        if not self.evaluation_hypotheses:
            raise ValueError(
                f"Fixture {self.case_id} must include hypotheses."
            )

    def to_dict(self) -> Dict[str, object]:
        self.validate()
        return asdict(self)


def fixture_cases() -> Tuple[ShadowFixtureCase, ...]:
    """
    Rubric-driven comparison cases.

    These cases define evaluation coverage before fixture evidence and mock
    planner responses are written. Hypotheses are review prompts, not expected
    planner outcomes.
    """
    return (
        ShadowFixtureCase(
            case_id="data_quality_strong_direct",
            user_goal=(
                "Build a data engineering project that helps teams detect "
                "pipeline data-quality failures and prioritize remediation."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Data Engineer"],
                "preferred_stack": ["Python", "FastAPI"],
            },
            coverage_tags=("strong_direct", "data_engineering"),
            evaluation_hypotheses=(
                "Both planners should have enough direct evidence to be "
                "meaningfully compared.",
                "Grounding and direction distinctiveness should be reviewable.",
            ),
            reviewer_focus=(
                "Does the planner create different operational angles rather "
                "than three validation-dashboard variants?"
            ),
        ),
        ShadowFixtureCase(
            case_id="rag_qa_strong_direct",
            user_goal=(
                "Build a retrieval augmented generation project for question "
                "answering that demonstrates evaluation and citation quality."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["ML Engineer"],
                "preferred_stack": ["Python", "FastAPI"],
            },
            coverage_tags=("strong_direct", "anchor_heavy", "rag_llm"),
            evaluation_hypotheses=(
                "Required query anchors should make evidence alignment clear.",
                "OpenAI uniqueness should be reviewed for usefulness, not just distance.",
            ),
            reviewer_focus=(
                "Do directions remain specifically about question answering "
                "rather than generic LLM applications?"
            ),
        ),
        ShadowFixtureCase(
            case_id="incident_investigation_broad",
            user_goal=(
                "Build a platform engineering project for incident "
                "investigation in three weeks."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Backend Engineer", "Platform Engineer"],
                "preferred_stack": ["Python", "React"],
            },
            coverage_tags=("broad_query", "adjacent_evidence", "platform"),
            evaluation_hypotheses=(
                "The brief may rely partly on adjacent planning evidence.",
                "Both_weak must remain available if the query is too broad.",
            ),
            reviewer_focus=(
                "Does each direction solve a concrete investigation workflow "
                "instead of merely naming a platform dashboard?"
            ),
        ),
        ShadowFixtureCase(
            case_id="developer_productivity_flaky_tests",
            user_goal=(
                "Build a developer productivity project that helps engineers "
                "identify flaky tests, connect failures with code changes, "
                "and prioritize likely root causes."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Developer Tools Engineer"],
                "preferred_stack": ["Python", "React"],
            },
            coverage_tags=("strong_direct", "multi_anchor", "developer_tools"),
            evaluation_hypotheses=(
                "Unique phrase diagnostics should be informative.",
                "Directions should differ across detection, correlation, and prioritization.",
            ),
            reviewer_focus=(
                "Is the candidate aligned with the combined flaky-test and "
                "code-change decision problem?"
            ),
        ),
        ShadowFixtureCase(
            case_id="sparse_evidence_cloud_cost",
            user_goal=(
                "Build a cloud cost optimization project that explains why "
                "specific resources are driving unexpected spend."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "2 weeks",
                "target_roles": ["Cloud Engineer"],
                "preferred_stack": ["Python"],
            },
            coverage_tags=("sparse", "cloud", "limited_evidence"),
            evaluation_hypotheses=(
                "Direct evidence may be limited.",
                "Manual review should distinguish useful exploration from "
                "overconfident research-backed framing.",
            ),
            reviewer_focus=(
                "Would an exploratory or limited-quality response be more "
                "honest than three confident recommendations?"
            ),
        ),
        ShadowFixtureCase(
            case_id="ambiguous_ai_student_project",
            user_goal=(
                "Build an AI project for students that can help me stand out "
                "for software engineering internships."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Software Engineer"],
                "preferred_stack": ["Python", "React"],
            },
            coverage_tags=("ambiguous_query", "career_context", "ai_ml"),
            evaluation_hypotheses=(
                "The query is underspecified enough to test ambiguity handling.",
                "Both planners may fail goal alignment despite domain relevance.",
            ),
            reviewer_focus=(
                "Does the planner resolve the user's actual decision problem "
                "without inventing a narrow intent?"
            ),
        ),
        ShadowFixtureCase(
            case_id="adversarial_cloud_incident_health_near_miss",
            user_goal=(
                "Build a cloud incident investigation project that correlates "
                "deployment changes with service-health events."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Platform Engineer"],
                "preferred_stack": ["Python", "FastAPI"],
            },
            coverage_tags=(
                "adversarial_near_miss",
                "strong_direct",
                "cloud_incidents",
            ),
            evaluation_hypotheses=(
                "The fixture should include an unrelated health-event source.",
                "Grounding review should expose citations that are valid but irrelevant.",
            ),
            reviewer_focus=(
                "Can reviewers distinguish source-ID validity from true "
                "candidate-to-source relevance?"
            ),
        ),
        ShadowFixtureCase(
            case_id="strict_weekend_scope",
            user_goal=(
                "Build a data engineering portfolio project that shows "
                "lineage-aware impact analysis for pipeline incidents."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "weekend",
                "target_roles": ["Data Engineer"],
                "preferred_stack": ["Python", "FastAPI"],
            },
            coverage_tags=("strict_scope", "feasibility", "data_engineering"),
            evaluation_hypotheses=(
                "Ambitious workflow candidates should trigger feasibility review.",
                "Scope realism may matter more than semantic novelty.",
            ),
            reviewer_focus=(
                "Does the MVP honestly fit the weekend constraint?"
            ),
        ),
        ShadowFixtureCase(
            case_id="no_research_paper_implementation_only",
            user_goal=(
                "Build a practical repository health tool that helps teams "
                "spot risky code ownership and dependency patterns."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "2 weeks",
                "target_roles": ["Backend Engineer"],
                "preferred_stack": ["Python"],
            },
            coverage_tags=(
                "no_research_paper",
                "implementation_context",
                "developer_tools",
            ),
            evaluation_hypotheses=(
                "The artifact should exercise missing-direct-research warnings.",
                "Promotion should not overstate evidence confidence.",
            ),
            reviewer_focus=(
                "Can the system remain helpful while clearly separating "
                "implementation context from research evidence?"
            ),
        ),
        ShadowFixtureCase(
            case_id="deterministic_template_risk",
            user_goal=(
                "Build a project that helps support engineers understand "
                "which downstream dashboards and owners are affected after "
                "a known data-quality incident."
            ),
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Data Engineer", "Backend Engineer"],
                "preferred_stack": ["Python", "PostgreSQL"],
            },
            coverage_tags=(
                "deterministic_risk",
                "distinctiveness",
                "data_engineering",
            ),
            evaluation_hypotheses=(
                "This case is intended to reveal generic deterministic "
                "template behavior if present.",
                "Unique OpenAI angles must still be judged for scope and grounding quality.",
            ),
            reviewer_focus=(
                "Does a distinctive angle create real planning value, or "
                "only semantic distance from template-shaped ideas?"
            ),
        ),
    )


def select_fixture_cases(
    case_ids: Optional[Sequence[str]] = None,
) -> Tuple[ShadowFixtureCase, ...]:
    cases = fixture_cases()

    for case in cases:
        case.validate()

    if case_ids is None:
        return cases

    requested = {
        str(case_id).strip()
        for case_id in case_ids
        if str(case_id).strip()
    }
    selected = tuple(
        case
        for case in cases
        if case.case_id in requested
    )

    missing = requested.difference(
        case.case_id
        for case in selected
    )

    if missing:
        raise ValueError(
            "Unknown fixture case IDs: " + ", ".join(sorted(missing))
        )

    return selected
