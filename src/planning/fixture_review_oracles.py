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
    )


def get_fixture_review_oracle(
    fixture_id: str,
) -> FixtureReviewOracle:
    for oracle in fixture_review_oracles():
        if oracle.fixture_id == fixture_id:
            oracle.validate()
            return oracle

    raise ValueError(f"No review oracle for fixture: {fixture_id}")
