from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Tuple

from planning.shadow_fixture_registry import (
    ShadowFixtureCase,
    select_fixture_cases,
)


_REQUIRED_CANDIDATE_FIELDS = {
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


@dataclass(frozen=True)
class ShadowFixtureSpecification:
    case: ShadowFixtureCase
    evidence_payload: Dict[str, Any]
    mock_response: Dict[str, Any]
    reviewability_requirements: Tuple[str, ...]

    def validate(self) -> None:
        self.case.validate()

        evidence_items = self.evidence_payload.get("merged_results", [])

        if not isinstance(evidence_items, list) or not evidence_items:
            raise ValueError(
                f"{self.case.case_id} must include non-empty merged_results."
            )

        known_source_ids = set()

        for item in evidence_items:
            if not isinstance(item, dict):
                raise ValueError(
                    f"{self.case.case_id} contains a non-mapping evidence item."
                )

            source_id = (
                item.get("source_id")
                or item.get("document_id")
                or item.get("repository_id")
                or item.get("id")
            )

            if not str(source_id or "").strip():
                raise ValueError(
                    f"{self.case.case_id} evidence requires a stable source ID."
                )

            if not str(item.get("source_type", "")).strip():
                raise ValueError(
                    f"{self.case.case_id} evidence requires source_type."
                )

            if not str(item.get("title", "")).strip():
                raise ValueError(
                    f"{self.case.case_id} evidence requires title."
                )

            known_source_ids.add(str(source_id).strip())

        candidates = self.mock_response.get("candidates", [])

        if not isinstance(candidates, list) or not candidates:
            raise ValueError(
                f"{self.case.case_id} must include mock candidates."
            )

        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError(
                    f"{self.case.case_id} contains a non-mapping candidate."
                )

            missing = sorted(
                _REQUIRED_CANDIDATE_FIELDS.difference(candidate)
            )

            if missing:
                raise ValueError(
                    f"{self.case.case_id} candidate missing fields: "
                    + ", ".join(missing)
                )

            unknown_ids = set(candidate["source_ids"]).difference(
                known_source_ids
            )

            if unknown_ids:
                raise ValueError(
                    f"{self.case.case_id} candidate cites unknown source IDs: "
                    + ", ".join(sorted(unknown_ids))
                )

        if not self.reviewability_requirements:
            raise ValueError(
                f"{self.case.case_id} needs reviewability requirements."
            )

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


def _case(case_id: str) -> ShadowFixtureCase:
    return select_fixture_cases([case_id])[0]


def fixture_specifications() -> Tuple[ShadowFixtureSpecification, ...]:
    """
    Concrete fixture specifications for controlled shadow evaluation.

    These establish that artifact schema, evidence provenance, candidate source
    IDs, and manual review templates are sufficient before expanding to all ten
    registry cases.
    """
    return (
        ShadowFixtureSpecification(
            case=_case("data_quality_strong_direct"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "data_engineering",
                },
                "merged_results": [
                    {
                        "document_id": "paper-quality",
                        "source_type": "research_paper",
                        "title": (
                            "Data Quality Monitoring for Reliable Pipelines"
                        ),
                        "abstract": (
                            "Data validation, anomaly detection, and "
                            "quality observability improve pipeline "
                            "reliability and remediation decisions."
                        ),
                        "category": "cs.DB",
                        "retrieval_rank": 1,
                    },
                    {
                        "document_id": "paper-lineage",
                        "source_type": "research_paper",
                        "title": (
                            "Lineage-Aware Impact Analysis for Data Incidents"
                        ),
                        "abstract": (
                            "Dataset lineage can identify downstream assets "
                            "affected by quality incidents and support "
                            "priority-based remediation."
                        ),
                        "category": "cs.DB",
                        "retrieval_rank": 2,
                    },
                    {
                        "repository_id": "repo-observability",
                        "source_type": "github_repository",
                        "title": "Pipeline Quality Observability Toolkit",
                        "readme_excerpt": (
                            "Track data checks, failed records, pipeline "
                            "owners, and quality trends for engineering teams."
                        ),
                        "retrieval_rank": 3,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "Pipeline Data-Quality Monitor",
                        "problem_statement": (
                            "Data engineers need a focused way to detect and "
                            "triage recurring quality failures in pipelines."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load representative pipeline quality events.",
                            "Run transparent validation checks.",
                            "Show failed checks and remediation priority.",
                        ],
                        "mvp_scope": [
                            "Load sample pipeline records and quality rules.",
                            "Run completeness and schema validation checks.",
                            "Store failed checks with timestamps.",
                            "Show a dashboard of active quality failures.",
                        ],
                        "success_metrics": [
                            "Number of detected quality failures."
                        ],
                        "evidence_relationship": (
                            "Uses direct evidence on data validation and "
                            "quality observability."
                        ),
                        "source_ids": ["paper-quality"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "Lineage Impact Explorer for Data Incidents",
                        "problem_statement": (
                            "Teams struggle to identify downstream datasets "
                            "and owners affected by a known quality incident."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load incident and lineage records.",
                            "Trace affected downstream assets.",
                            "Rank affected owners and dashboards.",
                        ],
                        "mvp_scope": [
                            "Store sample dataset lineage edges.",
                            "Load a known data-quality incident.",
                            "Compute affected downstream datasets.",
                            "Show an owner and impact report.",
                        ],
                        "success_metrics": [
                            "Time required to identify affected assets."
                        ],
                        "evidence_relationship": (
                            "Uses direct evidence on lineage-aware impact "
                            "analysis for incidents."
                        ),
                        "source_ids": ["paper-lineage"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "PostgreSQL"],
                    },
                    {
                        "title": "Quality Trend and Ownership Workbench",
                        "problem_statement": (
                            "Engineering teams need to see whether recurring "
                            "quality issues are concentrated by pipeline and "
                            "owner."
                        ),
                        "target_user": "Data platform teams",
                        "core_workflow": [
                            "Load historical quality events.",
                            "Group failures by pipeline and owner.",
                            "Review recurring issue trends.",
                        ],
                        "mvp_scope": [
                            "Load historical quality-event records.",
                            "Group failures by pipeline and owner.",
                            "Calculate recurring failure counts.",
                            "Show trend and ownership views.",
                        ],
                        "success_metrics": [
                            "Number of recurring issues surfaced."
                        ],
                        "evidence_relationship": (
                            "Uses implementation context for pipeline quality "
                            "observability workflows."
                        ),
                        "source_ids": ["repo-observability"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                ],
            },
            reviewability_requirements=(
                "Raw deterministic ideas are retained.",
                "Raw shadow candidates are retained.",
                "Candidate source IDs map to brief sources.",
                "Enriched outputs remain available for scope review.",
                "An unscored manual review template is present.",
            ),
        ),
        ShadowFixtureSpecification(
            case=_case("rag_qa_strong_direct"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "rag_llm",
                },
                "merged_results": [
                    {
                        "document_id": "paper-rag-evaluation",
                        "source_type": "research_paper",
                        "title": (
                            "Evaluation of Retrieval Augmented Generation "
                            "for Question Answering"
                        ),
                        "abstract": (
                            "Retrieval augmented generation for question "
                            "answering requires evaluation of answer "
                            "correctness, retrieved context relevance, and "
                            "failure cases."
                        ),
                        "category": "cs.CL",
                        "retrieval_rank": 1,
                    },
                    {
                        "document_id": "paper-citation-grounding",
                        "source_type": "research_paper",
                        "title": (
                            "Citation Grounding and Evidence Attribution in "
                            "Question Answering Systems"
                        ),
                        "abstract": (
                            "Question answering systems should connect answer "
                            "claims to cited passages, measure citation "
                            "faithfulness, and expose unsupported statements."
                        ),
                        "category": "cs.CL",
                        "retrieval_rank": 2,
                    },
                    {
                        "repository_id": "repo-rag-eval-dashboard",
                        "source_type": "github_repository",
                        "title": "RAG Question Answering Evaluation Dashboard",
                        "readme_excerpt": (
                            "Evaluate RAG question answering runs with "
                            "retrieval metrics, answer scores, citation "
                            "coverage, and per-question failure traces."
                        ),
                        "retrieval_rank": 3,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "RAG QA Citation Quality Workbench",
                        "problem_statement": (
                            "ML engineers need to verify whether generated "
                            "question-answering responses cite passages that "
                            "actually support answer claims."
                        ),
                        "target_user": "ML engineers",
                        "core_workflow": [
                            "Load question, answer, retrieved passage, and "
                            "citation records.",
                            "Check whether answer claims have cited evidence.",
                            "Show unsupported claims and missing citations.",
                        ],
                        "mvp_scope": [
                            "Load a small RAG question-answering evaluation "
                            "dataset.",
                            "Store questions, generated answers, retrieved "
                            "contexts, and cited passages.",
                            "Compute citation coverage per answer.",
                            "Show unsupported answer spans for review.",
                        ],
                        "success_metrics": [
                            "Percentage of answer claims with supporting citations.",
                            "Number of unsupported claims found.",
                        ],
                        "evidence_relationship": (
                            "Uses direct evidence on citation grounding and "
                            "evidence attribution for question answering."
                        ),
                        "source_ids": ["paper-citation-grounding"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "RAG Retrieval Failure Analyzer",
                        "problem_statement": (
                            "Teams need to identify whether wrong question "
                            "answering responses are caused by retrieval "
                            "failure or answer generation failure."
                        ),
                        "target_user": "ML engineers",
                        "core_workflow": [
                            "Load questions, retrieved contexts, and answers.",
                            "Score context relevance for each question.",
                            "Group failures by retrieval and answer quality.",
                        ],
                        "mvp_scope": [
                            "Load sample RAG evaluation runs.",
                            "Compare retrieved context terms with each question.",
                            "Label examples as retrieval miss or answer issue.",
                            "Show failure categories in a dashboard.",
                        ],
                        "success_metrics": [
                            "Number of QA failures categorized.",
                            "Share of failures caused by retrieval misses.",
                        ],
                        "evidence_relationship": (
                            "Uses direct RAG question-answering evaluation "
                            "evidence."
                        ),
                        "source_ids": ["paper-rag-evaluation"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "Question-Level RAG Evaluation Dashboard",
                        "problem_statement": (
                            "Students building RAG demos need a practical way "
                            "to inspect question-level answer quality, "
                            "retrieval quality, and citation coverage."
                        ),
                        "target_user": "ML engineering students",
                        "core_workflow": [
                            "Load RAG evaluation run outputs.",
                            "Calculate answer, retrieval, and citation metrics.",
                            "Inspect per-question failures.",
                        ],
                        "mvp_scope": [
                            "Load JSONL evaluation runs.",
                            "Calculate retrieval hit rate and citation coverage.",
                            "Show per-question answer quality notes.",
                            "Export a review summary for each run.",
                        ],
                        "success_metrics": [
                            "Number of evaluated QA examples.",
                            "Number of citation or retrieval failures surfaced.",
                        ],
                        "evidence_relationship": (
                            "Uses implementation context for RAG QA evaluation "
                            "dashboards."
                        ),
                        "source_ids": ["repo-rag-eval-dashboard"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                ],
            },
            reviewability_requirements=(
                "The fixture has direct RAG question-answering evidence.",
                "Citation quality and evaluation quality remain visible.",
                "Candidate source IDs map to exact brief sources.",
                "Manual review can distinguish QA-specific ideas from generic LLM apps.",
                "An unscored manual review template is present.",
            ),
        ),
        ShadowFixtureSpecification(
            case=_case("developer_productivity_flaky_tests"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "developer_tools",
                },
                "merged_results": [
                    {
                        "document_id": "paper-flaky-test-detection",
                        "source_type": "research_paper",
                        "title": (
                            "Detecting and Prioritizing Flaky Tests in "
                            "Continuous Integration"
                        ),
                        "abstract": (
                            "Flaky tests reduce developer productivity by "
                            "causing nondeterministic CI failures. Detection "
                            "uses repeated test outcomes, historical failure "
                            "patterns, and prioritization signals."
                        ),
                        "category": "cs.SE",
                        "retrieval_rank": 1,
                    },
                    {
                        "document_id": "paper-change-failure-correlation",
                        "source_type": "research_paper",
                        "title": (
                            "Connecting Test Failures with Code Changes for "
                            "Root Cause Analysis"
                        ),
                        "abstract": (
                            "Linking failing tests with recent code changes, "
                            "changed files, ownership, and commit metadata can "
                            "support root cause analysis in software testing."
                        ),
                        "category": "cs.SE",
                        "retrieval_rank": 2,
                    },
                    {
                        "repository_id": "repo-ci-failure-triage",
                        "source_type": "github_repository",
                        "title": "CI Failure Triage Dashboard",
                        "readme_excerpt": (
                            "Collect CI runs, failed tests, changed files, "
                            "commit authors, flaky-test labels, and failure "
                            "history to prioritize likely root causes."
                        ),
                        "retrieval_rank": 3,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "Flaky Test Detection Dashboard",
                        "problem_statement": (
                            "Developer tools teams need to identify tests "
                            "whose failures are likely nondeterministic rather "
                            "than caused by the latest code change."
                        ),
                        "target_user": "Developer Tools Engineers",
                        "core_workflow": [
                            "Load historical CI test outcomes.",
                            "Detect tests with inconsistent pass/fail history.",
                            "Rank likely flaky tests for triage.",
                        ],
                        "mvp_scope": [
                            "Load sample CI run and test result records.",
                            "Compute pass/fail variance per test.",
                            "Flag tests with repeated nondeterministic outcomes.",
                            "Show flaky-test candidates in a dashboard.",
                        ],
                        "success_metrics": [
                            "Number of likely flaky tests identified.",
                            "Precision of flaky-test labels on sample data.",
                        ],
                        "evidence_relationship": (
                            "Uses direct evidence on flaky-test detection and "
                            "prioritization in continuous integration."
                        ),
                        "source_ids": ["paper-flaky-test-detection"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "React"],
                    },
                    {
                        "title": "Code Change Failure Correlator",
                        "problem_statement": (
                            "Engineers need to understand whether failing "
                            "tests are related to recent commits, changed "
                            "files, or ownership signals."
                        ),
                        "target_user": "Software Engineers",
                        "core_workflow": [
                            "Load failed tests and recent commits.",
                            "Map changed files to failed test areas.",
                            "Show likely change-to-failure links.",
                        ],
                        "mvp_scope": [
                            "Load sample commit, changed-file, and failed-test data.",
                            "Create simple file-to-test ownership mappings.",
                            "Rank commits that may explain a test failure.",
                            "Show linked changes beside each failed test.",
                        ],
                        "success_metrics": [
                            "Number of failures linked to candidate changes.",
                            "Time saved during failure triage.",
                        ],
                        "evidence_relationship": (
                            "Uses direct evidence on connecting test failures "
                            "with code changes for root cause analysis."
                        ),
                        "source_ids": ["paper-change-failure-correlation"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "CI Root Cause Prioritization Queue",
                        "problem_statement": (
                            "Teams need a practical queue that combines flaky "
                            "test history, failed CI runs, changed files, and "
                            "ownership to prioritize likely root causes."
                        ),
                        "target_user": "Developer Tools Engineers",
                        "core_workflow": [
                            "Load CI runs, failed tests, and changed files.",
                            "Combine flaky-test and code-change signals.",
                            "Prioritize failures for engineer review.",
                        ],
                        "mvp_scope": [
                            "Load sample CI failure records.",
                            "Join failures with commits and changed files.",
                            "Add flaky-test history as a prioritization signal.",
                            "Show a ranked triage queue with explanations.",
                        ],
                        "success_metrics": [
                            "Number of CI failures prioritized.",
                            "Percentage of failures with an explainable root-cause hint.",
                        ],
                        "evidence_relationship": (
                            "Uses implementation context for CI failure triage "
                            "and direct signals from flaky-test and code-change "
                            "evidence."
                        ),
                        "source_ids": [
                            "repo-ci-failure-triage",
                            "paper-flaky-test-detection",
                            "paper-change-failure-correlation",
                        ],
                        "assumptions": [],
                        "suggested_stack": ["Python", "React"],
                    },
                ],
            },
            reviewability_requirements=(
                "The fixture has direct flaky-test and code-change evidence.",
                "The combined detection, correlation, and prioritization goal remains visible.",
                "Candidate source IDs map to exact brief sources.",
                "Manual review can distinguish generic CI dashboards from root-cause triage tools.",
                "An unscored manual review template is present.",
            ),
        ),
        ShadowFixtureSpecification(
            case=_case("adversarial_cloud_incident_health_near_miss"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "cloud_platform",
                },
                "merged_results": [
                    {
                        "document_id": "paper-cloud-incidents",
                        "source_type": "research_paper",
                        "title": (
                            "Event Correlation for Cloud Incident Investigation"
                        ),
                        "abstract": (
                            "Correlating deployment changes, service health, "
                            "and operational telemetry supports cloud incident "
                            "investigation."
                        ),
                        "category": "cs.SE",
                        "retrieval_rank": 1,
                    },
                    {
                        "document_id": "paper-health-events",
                        "source_type": "research_paper",
                        "title": "Continuous Health Event Retrieval",
                        "abstract": (
                            "Retrieve and summarize event sequences from "
                            "continuous personal health data."
                        ),
                        "category": "cs.CL",
                        "retrieval_rank": 2,
                    },
                    {
                        "repository_id": "repo-incident-timeline",
                        "source_type": "github_repository",
                        "title": "Cloud Incident Timeline Toolkit",
                        "readme_excerpt": (
                            "Combine deploy events, service-health metrics, "
                            "and incident notes into investigation timelines."
                        ),
                        "retrieval_rank": 3,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "Deployment-to-Incident Correlation Workbench",
                        "problem_statement": (
                            "Platform engineers need to inspect whether "
                            "deployment changes align with service-health "
                            "degradation during incidents."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load deployment and service-health events.",
                            "Correlate events in a time window.",
                            "Show a ranked incident timeline.",
                        ],
                        "mvp_scope": [
                            "Load sample deploy and service-health events.",
                            "Normalize timestamps into one timeline.",
                            "Calculate simple correlation signals.",
                            "Show likely deployment-to-incident links.",
                        ],
                        "success_metrics": [
                            "Time to identify related deployment events."
                        ],
                        "evidence_relationship": (
                            "Uses direct cloud incident correlation evidence."
                        ),
                        "source_ids": ["paper-cloud-incidents"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "Incident Timeline Evidence Explorer",
                        "problem_statement": (
                            "Investigators need a concise view of operational "
                            "events, health signals, and incident notes."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load incident evidence.",
                            "Order evidence by time.",
                            "Filter the timeline by affected service.",
                        ],
                        "mvp_scope": [
                            "Load sample incident records.",
                            "Merge deployment and health-event timestamps.",
                            "Filter timeline entries by service.",
                            "Show a focused incident timeline.",
                        ],
                        "success_metrics": [
                            "Number of relevant events shown per incident."
                        ],
                        "evidence_relationship": (
                            "Uses cloud incident implementation context."
                        ),
                        "source_ids": ["repo-incident-timeline"],
                        "assumptions": [],
                        "suggested_stack": ["Python", "React"],
                    },
                    {
                        "title": "Health Event Incident Correlator",
                        "problem_statement": (
                            "Teams need to correlate health events during "
                            "operational incidents."
                        ),
                        "target_user": "Platform engineers",
                        "core_workflow": [
                            "Load health events.",
                            "Correlate events.",
                        ],
                        "mvp_scope": [
                            "Load sample event records.",
                            "Correlate event sequences.",
                            "Show related events.",
                        ],
                        "success_metrics": [
                            "Number of correlated events."
                        ],
                        "evidence_relationship": (
                            "Uses event-retrieval evidence."
                        ),
                        "source_ids": ["paper-health-events"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                ],
            },
            reviewability_requirements=(
                "The near-miss health-event source remains visible.",
                "Candidate source IDs map to exact brief sources.",
                "Manual grounding review can distinguish valid IDs from relevance.",
                "An unscored manual review template is present.",
            ),
        ),
        ShadowFixtureSpecification(
            case=_case("strict_weekend_scope"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "data_engineering",
                },
                "merged_results": [
                    {
                        "document_id": "paper-lineage-impact",
                        "source_type": "research_paper",
                        "title": (
                            "Lineage-Aware Impact Analysis for Pipeline "
                            "Incidents"
                        ),
                        "abstract": (
                            "Pipeline incident response can use dataset "
                            "lineage graphs to identify downstream tables, "
                            "dashboards, owners, and remediation priority."
                        ),
                        "category": "cs.DB",
                        "retrieval_rank": 1,
                    },
                    {
                        "repository_id": "repo-lineage-demo",
                        "source_type": "github_repository",
                        "title": "Minimal Data Lineage Impact Demo",
                        "readme_excerpt": (
                            "Load table dependencies, mark one failed upstream "
                            "dataset, and list affected downstream assets and "
                            "owners for incident review."
                        ),
                        "retrieval_rank": 2,
                    },
                    {
                        "document_id": "paper-data-incident-triage",
                        "source_type": "research_paper",
                        "title": "Prioritizing Data Incident Remediation",
                        "abstract": (
                            "Data incident triage benefits from ranking "
                            "affected assets by business importance, ownership, "
                            "and dependency depth."
                        ),
                        "category": "cs.SE",
                        "retrieval_rank": 3,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "Weekend Lineage Impact Mapper",
                        "problem_statement": (
                            "Data engineers need a small weekend project that "
                            "shows which downstream tables and dashboards are "
                            "affected by one known pipeline incident."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load a small table-lineage graph.",
                            "Select one failed upstream dataset.",
                            "List affected downstream assets and owners.",
                        ],
                        "mvp_scope": [
                            "Create a CSV fixture of datasets, owners, and "
                            "lineage edges.",
                            "Select one failed upstream dataset.",
                            "Traverse downstream dependencies.",
                            "Show affected assets in a simple report.",
                        ],
                        "success_metrics": [
                            "Number of affected downstream assets identified.",
                            "Time to generate an impact report.",
                        ],
                        "evidence_relationship": (
                            "Uses direct lineage-aware impact analysis evidence "
                            "and keeps the MVP weekend-sized."
                        ),
                        "source_ids": [
                            "paper-lineage-impact",
                            "repo-lineage-demo",
                        ],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "Incident Owner Lookup Table",
                        "problem_statement": (
                            "Teams need a quick way to map affected datasets "
                            "from a known incident to responsible owners."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load affected datasets from a lineage traversal.",
                            "Join datasets with owner metadata.",
                            "Show owner contacts for incident follow-up.",
                        ],
                        "mvp_scope": [
                            "Create sample dataset-owner metadata.",
                            "Join impacted datasets with owners.",
                            "Sort affected assets by owner.",
                            "Export a small owner action list.",
                        ],
                        "success_metrics": [
                            "Percentage of affected assets with an assigned owner."
                        ],
                        "evidence_relationship": (
                            "Uses implementation context from the minimal "
                            "lineage demo and incident ownership signals."
                        ),
                        "source_ids": ["repo-lineage-demo"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                    {
                        "title": "Simple Remediation Priority Ranker",
                        "problem_statement": (
                            "Data incident responders need a lightweight way "
                            "to prioritize affected assets after lineage impact "
                            "analysis."
                        ),
                        "target_user": "Data engineers",
                        "core_workflow": [
                            "Load affected downstream assets.",
                            "Assign simple importance and depth scores.",
                            "Rank remediation priority.",
                        ],
                        "mvp_scope": [
                            "Create a small affected-asset fixture.",
                            "Add business importance and dependency depth.",
                            "Compute a transparent priority score.",
                            "Show the ranked remediation list.",
                        ],
                        "success_metrics": [
                            "Number of affected assets ranked for remediation."
                        ],
                        "evidence_relationship": (
                            "Uses data incident triage evidence for prioritizing "
                            "affected lineage assets."
                        ),
                        "source_ids": ["paper-data-incident-triage"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                ],
            },
            reviewability_requirements=(
                "The fixture has direct lineage-aware impact evidence.",
                "The weekend time constraint remains visible.",
                "Candidate source IDs map to exact brief sources.",
                "Manual review can judge whether both paths are useful but scope-limited.",
                "An unscored manual review template is present.",
            ),
        ),
        ShadowFixtureSpecification(
            case=_case("sparse_evidence_cloud_cost"),
            evidence_payload={
                "inference": {
                    "inferred_focus": "cloud_platform",
                },
                "merged_results": [
                    {
                        "document_id": "paper-resource-allocation",
                        "source_type": "research_paper",
                        "title": (
                            "Resource Allocation Trends in Distributed Systems"
                        ),
                        "abstract": (
                            "Resource allocation policies can improve "
                            "utilization across distributed workloads."
                        ),
                        "category": "cs.DC",
                        "retrieval_rank": 1,
                    },
                    {
                        "repository_id": "repo-billing-export",
                        "source_type": "github_repository",
                        "title": "Cloud Billing Export Examples",
                        "readme_excerpt": (
                            "Examples for exporting daily billing records "
                            "into tables for reporting and exploration."
                        ),
                        "retrieval_rank": 2,
                    },
                ],
            },
            mock_response={
                "candidates": [
                    {
                        "title": "Cloud Cost Optimization Command Center",
                        "problem_statement": (
                            "Cloud teams need one place to find, explain, "
                            "and optimize all unexpected infrastructure cost."
                        ),
                        "target_user": "Cloud engineers",
                        "core_workflow": [
                            "Load billing exports.",
                            "Identify expensive resources.",
                            "Recommend optimization actions.",
                        ],
                        "mvp_scope": [
                            "Load daily billing records.",
                            "Group costs by service.",
                            "Show top spending services.",
                            "Recommend generic savings actions.",
                        ],
                        "success_metrics": [
                            "Estimated monthly savings."
                        ],
                        "evidence_relationship": (
                            "Uses billing-export implementation context and "
                            "general resource-allocation research."
                        ),
                        "source_ids": [
                            "paper-resource-allocation",
                            "repo-billing-export",
                        ],
                        "assumptions": [],
                        "suggested_stack": ["Python", "FastAPI"],
                    },
                    {
                        "title": "FinOps Root-Cause Recommendation Engine",
                        "problem_statement": (
                            "Teams need automated explanations for unexpected "
                            "cloud spend and resource waste."
                        ),
                        "target_user": "Cloud engineers",
                        "core_workflow": [
                            "Load billing data.",
                            "Detect cost changes.",
                            "Generate root-cause recommendations.",
                        ],
                        "mvp_scope": [
                            "Load sample billing rows.",
                            "Detect daily spending changes.",
                            "Display generic cost explanations.",
                            "List possible optimization actions.",
                        ],
                        "success_metrics": [
                            "Number of cost changes explained."
                        ],
                        "evidence_relationship": (
                            "Adapts generic resource-allocation concepts to "
                            "cloud cost analysis."
                        ),
                        "source_ids": ["paper-resource-allocation"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                    {
                        "title": "Billing Export Spend Explorer",
                        "problem_statement": (
                            "Teams need a simple way to inspect spending "
                            "records from a cloud billing export."
                        ),
                        "target_user": "Cloud engineers",
                        "core_workflow": [
                            "Load billing exports.",
                            "Filter service spend.",
                            "Inspect daily cost trends.",
                        ],
                        "mvp_scope": [
                            "Load a billing export CSV.",
                            "Filter records by service.",
                            "Show daily spend totals.",
                            "Display top cost categories.",
                        ],
                        "success_metrics": [
                            "Number of billing records explored."
                        ],
                        "evidence_relationship": (
                            "Uses billing-export implementation context."
                        ),
                        "source_ids": ["repo-billing-export"],
                        "assumptions": [],
                        "suggested_stack": ["Python"],
                    },
                ],
            },
            reviewability_requirements=(
                "Evidence limitations remain visible to reviewers.",
                "The artifact does not contain an expected winner.",
                "The packet permits both_weak as an explicit outcome.",
                "Candidates expose any confidence beyond source support.",
            ),
        ),
    )


def get_fixture_specification(
    case_id: str,
) -> ShadowFixtureSpecification:
    for specification in fixture_specifications():
        if specification.case.case_id == case_id:
            specification.validate()
            return specification

    raise ValueError(f"No fixture specification for case: {case_id}")
