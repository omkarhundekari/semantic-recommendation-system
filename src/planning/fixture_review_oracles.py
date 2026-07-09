from dataclasses import asdict, dataclass
from typing import Dict, Tuple

from planning.manual_review_rubric import (
    PREFERENCE_OPTIONS,
    RESPONSE_QUALITY_OPTIONS,
)
from planning.shadow_fixture_registry import fixture_cases


@dataclass(frozen=True)
class FixtureReviewOracle:
    """
    Expected manual-evaluation behavior for a controlled fixture.

    Oracles are intentionally separate from generated artifacts so they do not
    bias reviewers and are not overwritten when artifacts are regenerated.
    """

    fixture_id: str
    expected_overall_preference: str
    expected_response_quality: str
    reviewer_expectations: Tuple[str, ...]
    rationale: str

    def validate(self) -> None:
        known_fixture_ids = {
            case.case_id
            for case in fixture_cases()
        }

        if self.fixture_id not in known_fixture_ids:
            raise ValueError(
                f"Unknown fixture ID for review oracle: {self.fixture_id}"
            )

        if self.expected_overall_preference not in PREFERENCE_OPTIONS:
            raise ValueError(
                "expected_overall_preference must be one of "
                f"{sorted(PREFERENCE_OPTIONS)}."
            )

        if self.expected_response_quality not in RESPONSE_QUALITY_OPTIONS:
            raise ValueError(
                "expected_response_quality must be one of "
                f"{sorted(RESPONSE_QUALITY_OPTIONS)}."
            )

        if not self.reviewer_expectations:
            raise ValueError(
                f"{self.fixture_id} must include reviewer expectations."
            )

        if not self.rationale.strip():
            raise ValueError(
                f"{self.fixture_id} must include an oracle rationale."
            )

    def to_dict(self) -> Dict[str, object]:
        self.validate()
        return asdict(self)


def fixture_review_oracles() -> Tuple[FixtureReviewOracle, ...]:
    """
    Ground-truth expectations for controlled fixtures.

    These records support regression review after humans score the packets.
    They are not passed into planner generation or artifact creation.
    """
    return (
        FixtureReviewOracle(
            fixture_id="sparse_evidence_cloud_cost",
            expected_overall_preference="both_weak",
            expected_response_quality="exploratory",
            reviewer_expectations=(
                "Neither path should receive a strong endorsement.",
                "Reviewers should identify limited direct evidence.",
                "Confident optimization claims should be penalized when "
                "sources provide only implementation context or adjacency.",
            ),
            rationale=(
                "This controlled case intentionally provides weak support for "
                "root-cause cloud-cost explanation. It tests whether the "
                "rubric permits both_weak instead of forcing a preference."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="data_quality_strong_direct",
            expected_overall_preference="openai",
            expected_response_quality="standard",
            reviewer_expectations=(
                "Reviewers should expect strong direct evidence for data "
                "quality monitoring, pipeline observability, and lineage-aware "
                "incident impact analysis.",
                "Candidate directions should stay focused on data-quality "
                "failure detection, prioritization, ownership, or remediation.",
                "The stronger path should produce distinct operational "
                "workflows rather than repeating one validation-dashboard "
                "template."
            ),
            rationale=(
                "This controlled case provides direct data-quality, "
                "observability, and lineage evidence. A standard quality "
                "shadow preference is expected when the selected directions "
                "remain grounded, realistic, and operationally distinct."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="rag_qa_strong_direct",
            expected_overall_preference="openai",
            expected_response_quality="standard",
            reviewer_expectations=(
                "Reviewers should expect strong direct evidence for RAG "
                "question answering, citation quality, and evaluation.",
                "Candidate directions should remain specifically about "
                "question answering rather than generic LLM applications.",
                "The stronger path should produce distinct evaluation, "
                "citation-grounding, or retrieval-quality workflows.",
            ),
            rationale=(
                "This controlled case is intended to test an anchor-heavy "
                "RAG question-answering goal with direct evidence. A standard "
                "quality outcome is expected only if the selected directions "
                "stay grounded in evaluation and citation quality."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="developer_productivity_flaky_tests",
            expected_overall_preference="openai",
            expected_response_quality="standard",
            reviewer_expectations=(
                "Reviewers should expect direct evidence for flaky-test "
                "detection, CI failure triage, and code-change correlation.",
                "Candidate directions should address the combined problem of "
                "identifying flaky tests, linking failures to changes, and "
                "prioritizing likely root causes.",
                "The stronger path should separate detection, correlation, "
                "and prioritization into distinct developer-tool workflows.",
            ),
            rationale=(
                "This controlled case is intended to test a multi-anchor "
                "developer-productivity goal with strong direct evidence. A "
                "standard quality outcome is expected only if directions stay "
                "focused on flaky tests, CI failures, code changes, and root "
                "cause prioritization rather than generic testing dashboards."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="adversarial_cloud_incident_health_near_miss",
            expected_overall_preference="openai",
            expected_response_quality="limited",
            reviewer_expectations=(
                "Reviewers should prefer the shadow path over the deterministic "
                "path because the deterministic candidates are off-goal "
                "meta-planning outputs.",
                "Reviewers should downgrade response quality because one "
                "shadow candidate cites only adjacent health-event evidence.",
                "The artifact should surface the grounding failure through "
                "candidate-to-source relevance diagnostics and quality warnings.",
            ),
            rationale=(
                "This adversarial case intentionally mixes direct cloud "
                "incident evidence with an adjacent personal-health source. "
                "The expected outcome is an openai preference because the "
                "shadow set contains useful cloud-incident workflows, but "
                "limited response quality because the selected set still "
                "includes an adjacent-only candidate."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="strict_weekend_scope",
            expected_overall_preference="tie",
            expected_response_quality="limited",
            reviewer_expectations=(
                "Reviewers should treat this as a deterministic-competitive "
                "case rather than a shadow-favored case.",
                "Both planner paths should stay focused on lineage-aware impact "
                "analysis for data incidents.",
                "Response quality should be downgraded if either path proposes "
                "more than a realistic weekend MVP."
            ),
            rationale=(
                "This controlled case is intended to reduce selection bias by "
                "giving the deterministic planner a narrow, familiar "
                "data-engineering problem. A tie is expected if both paths stay "
                "aligned and grounded, but limited quality is expected because "
                "the weekend constraint makes scope realism difficult."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="no_research_paper_implementation_only",
            expected_overall_preference="openai",
            expected_response_quality="limited",
            reviewer_expectations=(
                "Reviewers should verify that implementation context is not "
                "overstated as direct research evidence.",
                "The stronger planner path should remain useful for a practical "
                "repository-health tool while acknowledging limited grounding.",
                "Quality should be limited unless the artifact clearly separates "
                "repository evidence from research-paper support."
            ),
            rationale=(
                "This case tests whether the evaluator remains helpful when the "
                "available evidence is implementation-oriented rather than "
                "research-paper-backed. The expected preference favors the "
                "shadow path if it produces more specific repository-health "
                "workflows, but response quality should remain limited because "
                "the grounding is not strong direct research evidence."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="ambiguous_ai_student_project",
            expected_overall_preference="both_weak",
            expected_response_quality="exploratory",
            reviewer_expectations=(
                "Reviewers should penalize overconfident project recommendations "
                "when the user goal is broad and underspecified.",
                "Both planner paths should be judged on whether they acknowledge "
                "ambiguity instead of inventing a narrow AI project intent.",
                "Response quality should remain exploratory unless the artifact "
                "clearly frames the output as options requiring user clarification."
            ),
            rationale=(
                "This case represents a common vague user request: build an AI "
                "project that helps a student stand out. The expected result is "
                "both_weak/exploratory if the planners turn the broad career goal "
                "into confident project recommendations without enough intent, "
                "domain, or evidence constraints."
            ),
        ),
        FixtureReviewOracle(
            fixture_id="deterministic_template_risk",
            expected_overall_preference="openai",
            expected_response_quality="standard",
            reviewer_expectations=(
                "Reviewers should check whether deterministic candidates reuse "
                "generic data-engineering templates instead of addressing the "
                "specific downstream dashboard and owner-impact problem.",
                "The stronger planner path should produce distinct candidates "
                "around incident impact, ownership, and downstream dependency review.",
                "Response quality can be standard only if candidates are grounded, "
                "specific, and feasible for the stated three-week scope."
            ),
            rationale=(
                "This case directly targets deterministic template drift. The "
                "expected outcome favors the shadow path if it creates specific "
                "data-quality incident impact directions rather than broad pipeline "
                "monitoring or generic dashboard ideas."
            ),
        ),
    )


def get_fixture_review_oracle(
    fixture_id: str,
) -> FixtureReviewOracle:
    for oracle in fixture_review_oracles():
        if oracle.fixture_id == fixture_id:
            oracle.validate()
            return oracle

    raise ValueError(f"No review oracle for fixture: {fixture_id}")
