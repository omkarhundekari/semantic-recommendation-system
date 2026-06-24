from typing import List


TITLE_SPECIFIC_MVP_TEMPLATES = {
    "frontend architecture intelligence platform": [
        "Accept a GitHub repository URL or local frontend project folder.",
        "Parse routes, components, shared utilities, and package dependencies.",
        "Build a component-dependency graph and flag oversized or tightly coupled modules.",
        "Apply architecture rules for duplication, boundary violations, and route complexity.",
        "Show prioritized refactoring recommendations with affected files and rationale.",
        "Export an architecture-health report with before-and-after cleanup targets.",
    ],
    "security vulnerability prioritization engine": [
        "Load a sample vulnerability dataset with CVE ID, severity, exploitability, asset criticality, and remediation status.",
        "Normalize severity and business-impact fields into a consistent risk-scoring schema.",
        "Calculate a transparent priority score and show the factors contributing to each rank.",
        "Build an analyst triage queue with severity, owner, remediation status, and explanation filters.",
        "Evaluate the ranking against a hand-labeled sample of high-priority findings.",
    ],
    "security log anomaly detection platform": [
        "Load sample authentication, endpoint, or network log events into a normalized event schema.",
        "Create baseline behavior profiles for users, IP addresses, event types, and time windows.",
        "Detect unusual login, access, or network patterns using rule-based and statistical anomaly signals.",
        "Assign explainable risk scores and show the signals that triggered each alert.",
        "Build an analyst review queue with filters, investigation notes, and false-positive labels.",
    ],
    "zero trust policy analyzer": [
        "Load sample identity, role, resource, and access-policy records into a policy graph.",
        "Identify overly broad permissions, stale access, risky role combinations, and missing ownership.",
        "Score policy findings by blast radius, sensitivity, and likelihood of misuse.",
        "Show affected users, resources, and recommended least-privilege policy changes.",
        "Validate the analyzer against a curated set of intentionally risky policy examples.",
    ],
    "cloud cost optimization dashboard": [
        "Load a sample cloud billing export and resource inventory into normalized cost tables.",
        "Group spend by service, account, region, owner, and resource type.",
        "Detect idle resources, underused instances, unattached storage, and sudden cost increases.",
        "Estimate monthly savings for each recommendation using transparent assumptions.",
        "Build an approval queue for optimization actions with owner, confidence, and savings filters.",
    ],
    "model evaluation intelligence dashboard": [
        "Select a small reproducible dataset, target variable, and baseline model.",
        "Create train, validation, and test splits with a documented evaluation protocol.",
        "Compare baseline models across accuracy, precision, recall, calibration, and error slices.",
        "Show feature importance or explanation views for representative predictions.",
        "Build a dashboard that highlights model tradeoffs and deployment-readiness risks.",
    ],
}


TITLE_SPECIFIC_MVP_TEMPLATES.update({
    "cloud resource risk scanner": [
        "Load a sample cloud-resource inventory with configuration, ownership, exposure, and monitoring metadata.",
        "Apply rules for public exposure, missing encryption, weak IAM settings, stale credentials, and missing tags.",
        "Score each finding by blast radius, asset sensitivity, exploitability, and remediation urgency.",
        "Show a prioritized remediation queue with affected resources, owners, and recommended fixes.",
        "Validate scanner rules against a small set of intentionally misconfigured cloud resources.",
    ],
    "serverless observability platform": [
        "Ingest sample function logs, metrics, traces, invocation counts, errors, and cost records.",
        "Aggregate latency, cold-start, error-rate, throughput, and cost metrics by function and deployment version.",
        "Detect regressions, expensive functions, recurring failure signatures, and noisy error patterns.",
        "Show drill-down views for a single function, a single invocation, and an incident timeline.",
        "Create threshold-based alerts and document the expected response workflow for each alert type.",
    ],
})


DOMAIN_MVP_TEMPLATES = {
    "frontend": [
        "Accept a frontend repository, build report, or Lighthouse-style metrics export as input.",
        "Extract component, route, accessibility, bundle, and performance signals into structured records.",
        "Detect high-impact issues such as duplicated components, inaccessible controls, or slow routes.",
        "Rank fixes by user impact, engineering effort, and affected surface area.",
        "Show an interactive dashboard with issue details, affected files, and recommended next actions.",
    ],
    "backend": [
        "Define a small API contract, request schema, response schema, and validation rules.",
        "Persist representative records in PostgreSQL or a local prototype database.",
        "Implement core endpoints with error handling, pagination, and input validation.",
        "Record latency, error-rate, and workflow metrics for the main API path.",
        "Add automated tests for one successful request, one invalid request, and one failure case.",
    ],
    "full_stack": [
        "Define one user workflow, core entities, and a small relational data model.",
        "Build validated backend endpoints for the workflow and persist representative records.",
        "Create responsive frontend screens for input, review, and result states.",
        "Add authentication or a simple role simulation only where it supports the core workflow.",
        "Deploy or containerize a reproducible end-to-end demo with setup instructions.",
    ],
    "rag_llm": [
        "Load a small document collection and preserve source metadata for each chunk.",
        "Implement chunking, embeddings, retrieval, and ranked evidence selection.",
        "Generate answers with source citations and expose the retrieved context for inspection.",
        "Measure retrieval relevance, citation coverage, and unsupported-answer risk on sample questions.",
        "Build a debugging view for failed retrievals, weak chunks, and low-confidence answers.",
    ],
    "ai_ml": [
        "Select a small reproducible dataset, target variable, and baseline evaluation metric.",
        "Create documented train, validation, and test splits with preprocessing steps.",
        "Train a baseline model and compare results across meaningful error slices.",
        "Expose prediction explanations, confidence signals, and common failure cases.",
        "Build a dashboard for metrics, examples, and model-quality tradeoffs.",
    ],
    "mlops": [
        "Track one reproducible experiment with dataset version, parameters, metrics, and model version.",
        "Persist training and evaluation results for comparison across runs.",
        "Monitor drift, latency, error rate, and prediction-quality signals over time.",
        "Create alert thresholds and a review workflow for degraded model behavior.",
        "Document a simple promotion rule for moving a model from experiment to deployment-ready.",
    ],
    "data_engineering": [
        "Ingest a small source dataset into a staged raw table or file layer.",
        "Apply transformations and create a clean analytics-ready output table.",
        "Validate schema, freshness, null rates, duplicate records, and key business rules.",
        "Track pipeline status, row counts, failures, and transformation lineage.",
        "Build a monitoring view with failed checks and recommended remediation actions.",
    ],
    "databases": [
        "Create a small schema with realistic relationships and representative seed data.",
        "Write slow or inefficient sample queries and capture their query-plan behavior.",
        "Analyze indexes, joins, filters, and cardinality issues that affect performance.",
        "Recommend specific index or query rewrites with expected tradeoffs.",
        "Measure before-and-after execution time for the optimization examples.",
    ],
    "cloud": [
        "Load a sample billing export and cloud-resource inventory into normalized tables.",
        "Group spend and resource usage by service, account, region, owner, and environment.",
        "Detect idle resources, underused capacity, missing tags, and sudden cost changes.",
        "Estimate savings or risk reduction using transparent recommendation rules.",
        "Build an action queue with owner, confidence, estimated impact, and approval status.",
    ],
    "devops": [
        "Ingest sample CI/CD logs, test results, deployment records, or incident events.",
        "Normalize failures by pipeline step, service, error signature, and deployment version.",
        "Group recurring failures and identify flaky tests, risky releases, or slow stages.",
        "Show an incident timeline with likely causes, affected services, and recommended fixes.",
        "Add automated tests for log parsing and one failure-classification workflow.",
    ],
    "cybersecurity": [
        "Load sample vulnerability, identity, access-policy, or security-log records into a normalized schema.",
        "Apply transparent rules for severity, exposure, anomaly signals, ownership, and asset criticality.",
        "Calculate explainable risk scores and retain the factors behind every finding.",
        "Build an analyst triage queue with severity, owner, remediation status, and evidence filters.",
        "Evaluate results against a small hand-labeled set of risky and non-risky cases.",
    ],
    "blockchain": [
        "Load sample contract metadata or transaction records into a structured analysis dataset.",
        "Identify risky functions, unusual transaction patterns, or governance concentration signals.",
        "Calculate severity or risk scores with transparent rule explanations.",
        "Build a dashboard for affected contracts, wallets, proposals, or transactions.",
        "Validate findings against curated examples with known safe and risky cases.",
    ],
    "healthcare_ai": [
        "Load de-identified healthcare-style records with a clearly defined operational prediction task.",
        "Create a baseline model or rules engine with documented data limitations.",
        "Show predictions, confidence, feature explanations, and caution notes separately.",
        "Evaluate performance across representative cohorts and error slices.",
        "Document limitations, fairness concerns, and non-clinical-use boundaries.",
    ],
    "mobile": [
        "Define one mobile user flow and store its core data locally for offline-first use.",
        "Build responsive mobile screens for capture, review, and progress states.",
        "Implement offline persistence, sync simulation, and conflict-handling behavior.",
        "Track one meaningful user metric such as streak, completion, or expense pattern.",
        "Test the primary flow on representative small-screen layouts.",
    ],
    "education_tech": [
        "Model learner goals, current skills, completed topics, and target outcomes.",
        "Create a simple recommendation or progression rule for next learning steps.",
        "Show progress, weak areas, recommended resources, and confidence explanations.",
        "Capture feedback on whether recommendations were useful or completed.",
        "Evaluate recommendation quality on a small set of representative learner profiles.",
    ],
    "recommendation_systems": [
        "Create a small user-item or user-project interaction dataset.",
        "Implement a baseline ranking method with a documented relevance objective.",
        "Generate recommendations with explanations for why each item was selected.",
        "Measure ranking quality, coverage, diversity, and feedback signals.",
        "Build a dashboard for user profiles, recommendation results, and evaluation metrics.",
    ],
    "nlp": [
        "Create a labeled sample dataset for classification, extraction, or summarization.",
        "Build a baseline NLP pipeline with text preprocessing and explicit evaluation metrics.",
        "Show predictions or extracted fields with confidence and review states.",
        "Analyze common error categories and representative failure examples.",
        "Build a small interface for submitting text and inspecting model output.",
    ],
    "computer_vision": [
        "Create a small image dataset with representative positive, negative, and difficult examples.",
        "Build an OCR, detection, or classification baseline with reproducible preprocessing.",
        "Display predictions with confidence scores and visual overlays where appropriate.",
        "Track false positives, false negatives, and performance by image condition.",
        "Create a review workflow for correcting or labeling difficult examples.",
    ],
    "fintech": [
        "Load a sample transaction or customer-risk dataset with clear feature definitions.",
        "Create transparent anomaly or risk-scoring rules with explanation fields.",
        "Rank high-risk cases and show the factors contributing to each score.",
        "Build a review queue with threshold controls and false-positive labels.",
        "Evaluate the system on curated normal, suspicious, and borderline examples.",
    ],
    "developer_tools": [
        "Load repository, pull-request, issue, or code-quality metadata through a sample export or API fixture.",
        "Compute maintainability, ownership, review-risk, or technical-debt signals.",
        "Rank repositories, modules, or pull requests by impact and remediation urgency.",
        "Show drill-down evidence for each recommendation, including affected files or teams.",
        "Validate one scoring rule against a curated set of known risky and healthy examples.",
    ],
}


def normalize_domain(domain: str) -> str:
    aliases = {
        "security": "cybersecurity",
        "ai": "ai_ml",
        "ml": "ai_ml",
        "fullstack": "full_stack",
        "full-stack": "full_stack",
    }

    normalized = str(domain or "general").strip().lower()
    return aliases.get(normalized, normalized)


def get_domain_mvp_template(title: str, domain: str) -> List[str]:
    normalized_title = str(title or "").strip().lower()

    for title_key, steps in TITLE_SPECIFIC_MVP_TEMPLATES.items():
        if title_key in normalized_title:
            return list(steps)

    return list(DOMAIN_MVP_TEMPLATES.get(normalize_domain(domain), []))
