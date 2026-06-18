from typing import Dict, List


DOMAIN_ALIASES = {
    "security": "cybersecurity",
    "data": "data_engineering",
    "healthcare": "healthcare_ai",
    "education": "education_tech",
    "edtech": "education_tech",
    "fullstack": "full_stack",
    "full-stack": "full_stack",
    "ai": "ai_ml",
    "ml": "ai_ml"
}


DOMAIN_PROFILES = {
    "frontend": {
        "ideas": [
            ("Frontend Architecture Intelligence Platform", "Analyze frontend project requirements and recommend routing, state management, component hierarchy, testing strategy, and performance priorities."),
            ("Design System Quality Dashboard", "Evaluate reusable components, accessibility consistency, documentation quality, and design-system adoption across a frontend codebase."),
            ("Frontend Performance Optimization Assistant", "Detect performance, accessibility, and UX bottlenecks and recommend practical fixes for modern React applications.")
        ],
        "skills": ["React", "TypeScript", "Tailwind CSS", "UI Architecture", "Accessibility", "Performance Optimization", "Testing"],
        "roles": ["Frontend Engineer", "Full-Stack Engineer", "UI Engineer", "Design Systems Engineer"]
    },
    "backend": {
        "ideas": [
            ("API Reliability Intelligence Platform", "Monitor API latency, error rates, endpoint usage, contract drift, and service health with explainable reliability insights."),
            ("Microservice Dependency Risk Mapper", "Visualize microservice dependencies, detect risky service relationships, and estimate failure impact before deployment."),
            ("Backend Architecture Review Assistant", "Analyze backend project requirements and recommend database design, API structure, caching, queues, and observability strategy.")
        ],
        "skills": ["FastAPI", "PostgreSQL", "Docker", "API Design", "System Design", "Observability", "Redis"],
        "roles": ["Backend Engineer", "Platform Engineer", "API Engineer", "Software Engineer"]
    },
    "full_stack": {
        "ideas": [
            ("Full-Stack Product Intelligence Platform", "Convert a product idea into database schema, API plan, frontend views, authentication flow, and deployment roadmap."),
            ("SaaS Feature Planning Dashboard", "Help builders plan MVP features, user roles, billing-ready architecture, analytics, and release milestones."),
            ("User Workflow Automation Platform", "Build a full-stack system that captures user workflows, automates repeated tasks, and tracks productivity impact.")
        ],
        "skills": ["React", "FastAPI", "PostgreSQL", "Authentication", "Docker", "System Design", "Deployment"],
        "roles": ["Full-Stack Engineer", "Backend Engineer", "Product Engineer", "Software Engineer"]
    },
    "rag_llm": {
        "ideas": [
            ("RAG Evaluation Studio", "Evaluate retrieval quality, answer faithfulness, citation coverage, hallucination risk, and context relevance across RAG pipelines."),
            ("RAG Pipeline Debugging Workbench", "Break RAG failures into retrieval, chunking, reranking, prompting, citation, and grounding issues with actionable fixes."),
            ("Evidence-Grounded Research Assistant", "Help users search documents, compare sources, ask grounded questions, and export cited research summaries.")
        ],
        "skills": ["RAG", "Semantic Search", "FAISS / Vector Search", "Embeddings", "LLM Evaluation", "Citation Grounding", "Python"],
        "roles": ["AI Engineer", "LLM Application Engineer", "NLP Engineer", "Search Engineer"]
    },
    "ai_ml": {
        "ideas": [
            ("Model Evaluation Intelligence Dashboard", "Compare models across metrics, datasets, error slices, feature importance, and deployment readiness."),
            ("ML Prediction Monitoring Platform", "Track prediction quality, anomaly signals, feature drift, and model behavior over time."),
            ("Explainable ML Decision Assistant", "Generate model explanations, feature impact summaries, and risk notes for prediction-heavy applications.")
        ],
        "skills": ["Machine Learning", "Model Evaluation", "Feature Engineering", "Explainability", "Python", "Analytics Dashboards"],
        "roles": ["ML Engineer", "Data Scientist", "AI Engineer", "Applied ML Engineer"]
    },
    "mlops": {
        "ideas": [
            ("MLOps Experiment Tracking Platform", "Track experiments, metrics, datasets, model versions, and deployment readiness across ML workflows."),
            ("Model Drift Monitoring Dashboard", "Detect data drift, prediction drift, feature distribution shifts, and alert teams when model quality may degrade."),
            ("Inference Reliability Intelligence Platform", "Monitor inference latency, failure rates, model versions, and production-readiness risks.")
        ],
        "skills": ["MLOps", "Experiment Tracking", "Model Registry", "Model Monitoring", "Drift Detection", "CI/CD", "Python"],
        "roles": ["MLOps Engineer", "ML Engineer", "Platform Engineer", "Data Engineer"]
    },
    "data_engineering": {
        "ideas": [
            ("Data Pipeline Quality Monitor", "Monitor ETL pipelines for freshness, schema drift, missing values, anomalies, and broken transformations."),
            ("Data Lineage and Dependency Visualizer", "Map pipeline dependencies, upstream/downstream tables, transformations, and failure impact across data systems."),
            ("Warehouse Query and Cost Intelligence Dashboard", "Analyze SQL usage, expensive queries, warehouse cost patterns, and optimization opportunities.")
        ],
        "skills": ["Python", "SQL", "ETL", "Data Quality", "Airflow Concepts", "Data Validation", "Monitoring"],
        "roles": ["Data Engineer", "Analytics Engineer", "Backend Engineer", "Data Platform Engineer"]
    },
    "databases": {
        "ideas": [
            ("Database Query Optimization Assistant", "Analyze SQL queries, query plans, indexes, and schema patterns to recommend performance improvements."),
            ("PostgreSQL Index Recommendation Engine", "Detect slow query patterns and recommend indexes with tradeoff explanations."),
            ("Database Migration Risk Analyzer", "Evaluate schema migrations for breaking changes, risky operations, rollback complexity, and test coverage.")
        ],
        "skills": ["SQL", "PostgreSQL", "Indexing", "Query Optimization", "Schema Design", "Database Performance"],
        "roles": ["Database Engineer", "Backend Engineer", "Data Engineer", "Platform Engineer"]
    },
    "cloud": {
        "ideas": [
            ("Cloud Cost Optimization Dashboard", "Analyze cloud resources, unused services, cost trends, and right-sizing opportunities with FinOps-style recommendations."),
            ("Cloud Resource Risk Scanner", "Detect misconfigured resources, risky access patterns, monitoring gaps, and cost-risk tradeoffs."),
            ("Serverless Observability Platform", "Track function latency, cold starts, errors, logs, and cost impact for serverless workloads.")
        ],
        "skills": ["Cloud Architecture", "AWS Concepts", "Cost Optimization", "Monitoring", "DevOps", "Dashboards", "Automation"],
        "roles": ["Cloud Engineer", "DevOps Engineer", "Platform Engineer", "SRE"]
    },
    "devops": {
        "ideas": [
            ("CI/CD Failure Intelligence Platform", "Analyze pipeline failures, group similar errors, detect flaky tests, and recommend fixes from logs."),
            ("Deployment Risk Scoring System", "Score release risk using test results, changed files, service dependencies, incidents, and deployment history."),
            ("Incident Postmortem Generator", "Convert logs, alerts, and timeline events into structured postmortems with action items.")
        ],
        "skills": ["CI/CD", "Docker", "GitHub Actions", "Logs", "Monitoring", "Automation", "Reliability"],
        "roles": ["DevOps Engineer", "Platform Engineer", "SRE", "Software Engineer"]
    },
    "cybersecurity": {
        "ideas": [
            ("Security Vulnerability Prioritization Engine", "Rank vulnerabilities by severity, exploitability, affected systems, and business impact."),
            ("Security Log Anomaly Detection Platform", "Detect unusual login, network, and access patterns from security logs with explainable risk scores."),
            ("Zero Trust Policy Analyzer", "Analyze access policies, risky permissions, identity relationships, and policy gaps.")
        ],
        "skills": ["Cybersecurity Analytics", "Risk Scoring", "Threat Modeling", "Log Analysis", "APIs", "Dashboards"],
        "roles": ["Security Engineer", "Cybersecurity Analyst", "Detection Engineer", "DevSecOps Engineer"]
    },
    "blockchain": {
        "ideas": [
            ("Smart Contract Risk Analyzer", "Scan smart contract patterns for common vulnerabilities, risky functions, and severity-ranked findings."),
            ("DeFi Transaction Risk Dashboard", "Analyze blockchain transaction flows, wallet behavior, and risk indicators for suspicious financial activity."),
            ("DAO Governance Analytics Platform", "Track voting behavior, proposal outcomes, participation trends, and governance concentration.")
        ],
        "skills": ["Blockchain", "Smart Contracts", "Solidity Concepts", "Security Analysis", "Transaction Graphs", "Risk Scoring"],
        "roles": ["Blockchain Engineer", "Security Engineer", "Backend Engineer", "Web3 Engineer"]
    },
    "healthcare_ai": {
        "ideas": [
            ("Healthcare Risk Prediction Dashboard", "Predict healthcare operational risks such as no-shows, readmissions, or delayed follow-ups using explainable analytics."),
            ("Clinical Document Intelligence Assistant", "Summarize clinical notes, extract key information, and provide grounded document search for healthcare teams."),
            ("Medication Interaction Risk Checker", "Identify medication interaction risks and explain possible concerns using structured healthcare knowledge.")
        ],
        "skills": ["Healthcare Analytics", "Machine Learning", "NLP", "Risk Scoring", "Dashboards", "Data Validation"],
        "roles": ["Healthcare AI Engineer", "ML Engineer", "Data Scientist", "Healthcare Data Analyst"]
    },
    "mobile": {
        "ideas": [
            ("Offline-First Mobile Productivity App", "Build a mobile app with offline storage, sync conflict handling, reminders, and personalized user insights."),
            ("Mobile Habit Intelligence Tracker", "Track habits, detect behavior patterns, and generate weekly improvement recommendations."),
            ("Mobile Expense Risk Alert App", "Analyze spending behavior and detect unusual subscriptions, spikes, or risky transactions.")
        ],
        "skills": ["React Native", "Mobile UI", "Offline Sync", "Analytics", "Notifications", "Personalization"],
        "roles": ["Mobile Engineer", "Full-Stack Engineer", "Product Engineer"]
    },
    "education_tech": {
        "ideas": [
            ("Student Learning Path Recommendation System", "Recommend personalized learning paths based on goals, current skills, weak areas, and target roles."),
            ("AI Tutor Progress Analytics Dashboard", "Track learning progress, confusion patterns, topic mastery, and personalized next steps."),
            ("Course Difficulty Prediction Tool", "Predict course difficulty and workload using historical signals, skills, and student feedback.")
        ],
        "skills": ["Recommendation Systems", "Learning Analytics", "Skill Mapping", "Dashboards", "Personalization"],
        "roles": ["EdTech Engineer", "Full-Stack Engineer", "AI Engineer", "Data Scientist"]
    },
    "recommendation_systems": {
        "ideas": [
            ("Explainable Recommendation Engine", "Recommend items, projects, or content while explaining why each recommendation fits the user."),
            ("Personalization Analytics Dashboard", "Track user behavior, ranking quality, feedback loops, and recommendation performance."),
            ("Career Path Recommendation Engine", "Recommend roles, skills, and projects based on user background and target career direction.")
        ],
        "skills": ["Recommendation Systems", "Ranking", "Personalization", "User Modeling", "Explainability"],
        "roles": ["ML Engineer", "Search Engineer", "Backend Engineer", "Data Scientist"]
    },
    "nlp": {
        "ideas": [
            ("Support Ticket Classification Platform", "Classify customer tickets, route them to teams, and explain urgency or topic predictions."),
            ("Meeting Transcript Action Item Extractor", "Extract decisions, owners, deadlines, and action items from meeting transcripts."),
            ("Document Clause Risk Analyzer", "Analyze long documents, extract clauses, and flag risky or unusual language.")
        ],
        "skills": ["NLP", "Text Classification", "Information Extraction", "Summarization", "Evaluation"],
        "roles": ["NLP Engineer", "AI Engineer", "Backend Engineer", "Data Scientist"]
    },
    "computer_vision": {
        "ideas": [
            ("OCR Receipt Intelligence Platform", "Extract structured data from receipt images, categorize expenses, and detect unusual spending patterns."),
            ("Construction Safety Detection Dashboard", "Detect safety equipment, unsafe behavior, or site risks from images and summarize compliance trends."),
            ("Retail Shelf Monitoring System", "Detect products, empty shelves, misplaced items, and inventory issues from shelf images.")
        ],
        "skills": ["Computer Vision", "OCR", "Object Detection", "Image Processing", "Model Evaluation", "Dashboards"],
        "roles": ["Computer Vision Engineer", "ML Engineer", "AI Engineer", "Data Scientist"]
    },
    "fintech": {
        "ideas": [
            ("Fraud Transaction Risk Scoring Dashboard", "Score transactions for fraud risk using behavioral signals, anomaly detection, and explainable risk factors."),
            ("Credit Risk Explanation Platform", "Explain credit risk decisions using model outputs, customer features, and fairness-aware summaries."),
            ("Subscription Spend Intelligence Tool", "Analyze recurring payments, categorize spending, and detect wasteful or unusual subscriptions.")
        ],
        "skills": ["Fraud Detection", "Risk Scoring", "Financial Analytics", "Machine Learning", "Explainability", "Dashboards"],
        "roles": ["FinTech Engineer", "ML Engineer", "Data Scientist", "Backend Engineer"]
    },
    "developer_tools": {
        "ideas": [
            ("Repository Health Intelligence Dashboard", "Analyze repository activity, code quality signals, issue patterns, pull requests, and maintenance risks."),
            ("Code Review Risk Assistant", "Score pull requests for risky changes, missing tests, unclear ownership, and architectural impact."),
            ("Technical Debt Prioritization Engine", "Identify technical debt areas and rank them by impact, frequency, complexity, and developer pain.")
        ],
        "skills": ["Developer Tools", "GitHub APIs", "Code Analysis", "Risk Scoring", "Dashboards", "Automation"],
        "roles": ["Developer Tools Engineer", "Software Engineer", "Platform Engineer", "Engineering Productivity Engineer"]
    },
    "general": {
        "ideas": [
            ("Project Opportunity Discovery Engine", "Turn technical evidence into buildable project opportunities with scope, risks, and career signal."),
            ("Technical Roadmap Recommendation System", "Generate learning paths, project roadmaps, and role alignment from user goals."),
            ("Evidence-Grounded Portfolio Planner", "Recommend portfolio projects grounded in evidence, skills, and target roles.")
        ],
        "skills": ["Full-Stack Development", "Project Planning", "APIs", "Dashboards", "Analytics"],
        "roles": ["Software Engineer", "Full-Stack Engineer", "Product Engineer"]
    }
}


THEME_KEYWORDS = {
    "retrieval": ["retrieval", "semantic search", "vector", "embedding", "rag"],
    "evaluation": ["evaluation", "metrics", "score", "quality", "faithfulness", "risk"],
    "monitoring": ["monitor", "observability", "logs", "alerts", "dashboard"],
    "automation": ["automation", "assistant", "recommend", "generate", "workflow"],
    "security": ["security", "vulnerability", "threat", "risk", "zero trust"],
    "performance": ["performance", "latency", "optimization", "cost", "speed"],
    "explainability": ["explain", "interpret", "why", "reason", "evidence"],
    "data_quality": ["data quality", "schema", "drift", "validation", "pipeline"]
}


def build_project_intelligence(
    evidence_items: List[Dict],
    user_query: str,
    detected_domain: str,
    max_ideas: int = 3
) -> Dict:
    domain = normalize_domain(detected_domain)
    combined_text = build_combined_text(evidence_items, user_query)

    themes = extract_project_themes(combined_text, domain)
    skills = extract_technical_skills(combined_text, domain)
    opportunities = identify_project_opportunities(combined_text, domain)

    blueprints = generate_diverse_project_ideas(
        evidence_items=evidence_items,
        user_query=user_query,
        detected_domain=domain,
        themes=themes,
        skills=skills,
        opportunities=opportunities,
        max_ideas=max_ideas
    )

    return {
        "detected_domain": domain,
        "themes": themes,
        "skills": skills,
        "opportunities": opportunities,
        "idea_blueprints": blueprints
    }


def build_combined_text(evidence_items: List[Dict], user_query: str) -> str:
    parts = [user_query]

    for item in evidence_items:
        for key in ["title", "content", "abstract", "category", "tags", "skills", "target_roles", "project_type"]:
            value = item.get(key, "")
            if isinstance(value, list):
                parts.extend(str(v) for v in value)
            else:
                parts.append(str(value))

    return " ".join(parts).lower()


def extract_project_themes(text: str, detected_domain: str) -> List[str]:
    themes = []

    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            themes.append(theme.replace("_", " ").title())

    domain_label = normalize_domain(detected_domain).replace("_", " ").title()

    if domain_label not in themes:
        themes.insert(0, domain_label)

    return themes[:6]


def extract_technical_skills(text: str, detected_domain: str) -> List[str]:
    domain = normalize_domain(detected_domain)
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])

    skills = []

    for skill in profile["skills"]:
        if skill not in skills:
            skills.append(skill)

    evidence_skill_candidates = [
        "React", "TypeScript", "Tailwind CSS", "FastAPI", "PostgreSQL", "Docker",
        "Semantic Search", "RAG", "LLM Evaluation", "Machine Learning", "SQL",
        "Cybersecurity Analytics", "Cloud Architecture", "CI/CD", "MLOps",
        "Data Quality", "Computer Vision", "NLP", "Risk Scoring", "GitHub APIs"
    ]

    for skill in evidence_skill_candidates:
        if skill.lower() in text and skill not in skills:
            skills.append(skill)

    return skills[:10]


def identify_project_opportunities(text: str, detected_domain: str) -> List[str]:
    domain = normalize_domain(detected_domain)
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])

    opportunities = []

    for _, angle in profile["ideas"]:
        opportunities.append(angle)

    return opportunities[:5]


def generate_diverse_project_ideas(
    evidence_items: List[Dict],
    user_query: str,
    detected_domain: str,
    themes: List[str],
    skills: List[str],
    opportunities: List[str],
    max_ideas: int = 3
) -> List[Dict]:
    domain = normalize_domain(detected_domain)
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])
    idea_bank = profile["ideas"]

    blueprints = []

    for index in range(max_ideas):
        if index < len(idea_bank):
            title, angle = idea_bank[index]
        else:
            title, angle = idea_bank[index % len(idea_bank)]

        evidence_item = evidence_items[index % len(evidence_items)] if evidence_items else {}
        blueprint = build_idea_blueprint(
            title=title,
            angle=angle,
            evidence_item=evidence_item,
            detected_domain=domain,
            themes=themes,
            skills=skills,
            opportunities=opportunities,
            index=index
        )
        blueprints.append(blueprint)

    return blueprints


def build_idea_blueprint(
    title: str,
    angle: str,
    evidence_item: Dict,
    detected_domain: str,
    themes: List[str],
    skills: List[str],
    opportunities: List[str],
    index: int
) -> Dict:
    evidence_title = evidence_item.get("title", "")
    evidence_category = evidence_item.get("category", detected_domain)

    refined_skills = refine_skills_for_idea(
        title=title,
        angle=angle,
        detected_domain=detected_domain,
        base_skills=skills
    )

    return {
        "project_title": title,
        "idea_angle": angle,
        "opportunity": opportunities[index % len(opportunities)] if opportunities else angle,
        "themes": themes,
        "skills": refined_skills,
        "evidence_title": evidence_title,
        "evidence_category": evidence_category,
        "detected_domain": detected_domain
    }


def refine_skills_for_idea(
    title: str,
    angle: str,
    detected_domain: str,
    base_skills: List[str]
) -> List[str]:
    title_lower = title.lower()
    angle_lower = angle.lower()
    combined = f"{title_lower} {angle_lower}"
    domain = normalize_domain(detected_domain)

    idea_skill_map = {
        "receipt": ["OCR", "Document Processing", "Data Extraction", "Image Processing", "Expense Categorization", "Dashboards"],
        "construction safety": ["Computer Vision", "Object Detection", "Safety Analytics", "Image Processing", "Model Evaluation", "Dashboards"],
        "retail shelf": ["Computer Vision", "Object Detection", "Inventory Analytics", "Image Processing", "Model Evaluation", "Dashboards"],

        "fraud transaction": ["Fraud Detection", "Risk Scoring", "Anomaly Detection", "Financial Analytics", "Explainability", "Dashboards"],
        "credit risk": ["Credit Risk Modeling", "Explainability", "Financial Analytics", "Model Evaluation", "Fairness Awareness", "Dashboards"],
        "subscription spend": ["Financial Analytics", "Spend Categorization", "Recurring Payment Detection", "Dashboards", "Budget Insights", "Data Visualization"],

        "repository health": ["GitHub APIs", "Repository Analytics", "Code Quality Metrics", "Maintenance Risk Scoring", "Dashboards", "Automation"],
        "code review risk": ["Code Analysis", "Pull Request Analytics", "Risk Scoring", "Testing Signals", "GitHub APIs", "Developer Tools"],
        "technical debt": ["Code Metrics", "Technical Debt Analysis", "Prioritization", "Architecture Signals", "Dashboards", "Developer Tools"],

        "experiment tracking": ["MLOps", "Experiment Tracking", "Model Registry", "Metrics Tracking", "Model Versioning", "Python"],
        "model drift": ["Drift Detection", "Model Monitoring", "Feature Distribution Analysis", "Alerting", "MLOps", "Python"],
        "inference reliability": ["Inference Monitoring", "Latency Tracking", "Reliability Metrics", "Model Serving", "Observability", "MLOps"],

        "healthcare risk": ["Healthcare Analytics", "Predictive Modeling", "Risk Scoring", "Feature Engineering", "Dashboards", "Data Validation"],
        "clinical document": ["Healthcare NLP", "Summarization", "Information Extraction", "Document Search", "Evaluation", "Data Privacy Awareness"],
        "medication interaction": ["Healthcare Knowledge Graphs", "Risk Scoring", "Clinical Data Modeling", "Rule-Based Validation", "Explainability", "Data Safety"],

        "data pipeline": ["Data Quality", "ETL", "SQL", "Pipeline Monitoring", "Schema Validation", "Data Freshness"],
        "data lineage": ["Data Lineage", "Dependency Mapping", "ETL", "Impact Analysis", "SQL", "Data Platform Design"],
        "warehouse query": ["SQL", "Query Optimization", "Cost Analysis", "Warehouse Analytics", "Dashboarding", "Performance Tuning"]
    }

    selected_skills = []

    for key, skills in idea_skill_map.items():
        if key in combined:
            selected_skills = skills
            break

    if not selected_skills:
        selected_skills = list(base_skills)

    domain_fallbacks = {
        "computer_vision": ["Computer Vision", "Image Processing"],
        "fintech": ["Financial Analytics", "Risk Scoring"],
        "developer_tools": ["Developer Tools", "Automation"],
        "mlops": ["MLOps", "Model Monitoring"],
        "healthcare_ai": ["Healthcare Analytics", "Data Validation"],
        "data_engineering": ["Data Engineering", "SQL"]
    }

    selected_skills.extend(domain_fallbacks.get(domain, []))

    deduped = []
    for skill in selected_skills:
        if skill and skill not in deduped:
            deduped.append(skill)

    return deduped[:8]



def build_fallback_blueprint(
    evidence_item: Dict,
    user_query: str,
    detected_domain: str,
    index: int
) -> Dict:
    domain = normalize_domain(detected_domain)
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])
    title, angle = profile["ideas"][index % len(profile["ideas"])]

    return {
        "project_title": title,
        "idea_angle": angle,
        "opportunity": angle,
        "themes": [domain.replace("_", " ").title()],
        "skills": profile["skills"],
        "evidence_title": evidence_item.get("title", ""),
        "evidence_category": evidence_item.get("category", domain),
        "detected_domain": domain
    }


def infer_domain_from_query(query: str) -> str:
    query = query.lower()

    for domain in DOMAIN_PROFILES:
        readable = domain.replace("_", " ")
        if readable in query:
            return domain

    return "general"


def build_mvp_from_blueprint(blueprint: Dict) -> List[str]:
    title = blueprint.get("project_title", "Project")
    domain = normalize_domain(blueprint.get("detected_domain", "general"))

    base = [
        f"Create the core workflow for {title}.",
        "Build a simple input form or upload flow for the user query or project data.",
        "Store structured project/evidence records in a local database or CSV-backed prototype.",
        "Show ranked outputs with clear explanations and confidence signals.",
        "Add a dashboard view for results, scores, and recommended next actions."
    ]

    domain_specific = {
        "rag_llm": "Evaluate answer grounding, citations, retrieval quality, and hallucination risk.",
        "mlops": "Track model metrics, versions, drift signals, and deployment-readiness checks.",
        "data_engineering": "Validate schema, freshness, missing values, anomalies, and pipeline status.",
        "cybersecurity": "Score risks, explain suspicious signals, and prioritize remediation actions.",
        "computer_vision": "Process sample images, show detections or extracted text, and display confidence scores.",
        "fintech": "Score financial risk signals and explain the factors behind each decision.",
        "healthcare_ai": "Use sample healthcare-style records and clearly separate prediction, explanation, and caution notes.",
        "developer_tools": "Analyze repository or code-review style inputs and generate engineering productivity insights.",
        "cloud": "Track resources, costs, risk signals, and optimization recommendations.",
        "devops": "Ingest logs or pipeline results and group failures with recommended fixes.",
        "frontend": "Build reusable UI components, responsive views, and accessibility/performance checks.",
        "backend": "Expose API endpoints, validation logic, persistence, and observability-friendly outputs."
    }

    if domain in domain_specific:
        base.append(domain_specific[domain])

    return base



def augment_mvp_with_implementation_signals(
    mvp_scope: List[str],
    implementation_signals: List[str]
) -> List[str]:
    """
    Adds a small number of evidence-informed MVP steps when a project idea
    is grounded by an enriched GitHub implementation reference.
    """
    signal_steps = {
        "document_ingestion": (
            "Add a document-ingestion pipeline that validates files and "
            "prepares structured records for downstream processing."
        ),
        "retrieval_and_search": (
            "Implement semantic retrieval with ranked results and clear "
            "evidence links for each response or recommendation."
        ),
        "vector_database": (
            "Store embeddings in a lightweight vector index and support "
            "similarity-based retrieval."
        ),
        "knowledge_graph": (
            "Model important entities and relationships so users can inspect "
            "connections behind the recommendation."
        ),
        "api_service_layer": (
            "Expose the core workflow through validated API endpoints with "
            "structured request and response models."
        ),
        "web_dashboard": (
            "Add an interactive dashboard for filters, metrics, and drill-down "
            "views of the generated findings."
        ),
        "evaluation_and_monitoring": (
            "Capture evaluation metrics and monitoring signals so users can "
            "compare quality, reliability, or risk across runs."
        ),
        "experiment_tracking": (
            "Record experiment configurations, metrics, and model versions "
            "for reproducible comparisons."
        ),
        "deployment_and_containers": (
            "Containerize the prototype so the workflow runs consistently "
            "across local development and deployment environments."
        ),
        "cloud_and_serverless": (
            "Add a cloud-oriented integration layer for resource, service, "
            "or serverless workload inputs."
        ),
        "fraud_and_risk_modeling": (
            "Include risk scoring, anomaly flags, and explanation fields for "
            "each suspicious transaction or decision."
        ),
        "clinical_nlp": (
            "Use de-identified healthcare-style text or records and clearly "
            "separate model output from safety and limitation notes."
        ),
        "computer_vision": (
            "Process sample images or video frames and show detections with "
            "confidence scores and review-friendly output."
        ),
    }

    augmented_scope = list(mvp_scope)

    for signal in implementation_signals:
        step = signal_steps.get(signal)

        if step and step not in augmented_scope:
            augmented_scope.append(step)

        # Preserve an achievable MVP. Advanced work stays in extensions.
        if len(augmented_scope) >= len(mvp_scope) + 2:
            break

    return augmented_scope


def augment_tech_stack_with_implementation_technologies(
    tech_stack: List[str],
    implementation_technologies: List[str]
) -> List[str]:
    """
    Keeps the domain-based stack, but gives concrete technologies observed
    in a trusted implementation reference priority in the final list.
    """
    reference_technologies = []

    for technology in implementation_technologies:
        technology = str(technology).strip()

        if technology and technology not in reference_technologies:
            reference_technologies.append(technology)

    if not reference_technologies:
        return tech_stack[:12]

    generic_equivalents = {
        "AWS": {"AWS Concepts"},
        "OpenCV": {"OpenCV Concepts"},
    }

    filtered_stack = []

    for technology in tech_stack:
        is_generic_duplicate = any(
            technology in generic_names
            and concrete_name in reference_technologies
            for concrete_name, generic_names in generic_equivalents.items()
        )

        if technology in reference_technologies or is_generic_duplicate:
            continue

        if technology not in filtered_stack:
            filtered_stack.append(technology)

    max_reference_items = min(len(reference_technologies), 3)
    max_base_items = 12 - max_reference_items

    return (
        filtered_stack[:max_base_items]
        + reference_technologies[:max_reference_items]
    )[:12]


def build_advanced_features_from_blueprint(blueprint: Dict) -> List[str]:
    domain = normalize_domain(blueprint.get("detected_domain", "general"))

    features = [
        "Add user feedback loops to improve ranking and recommendations.",
        "Add export to JSON for GitHub, resume, or LinkedIn documentation.",
        "Add historical analytics so users can compare runs over time.",
        "Add explainability notes showing why each recommendation was produced."
    ]

    domain_features = {
        "rag_llm": [
            "Add side-by-side retrieval strategy comparison.",
            "Add citation coverage scoring and answer faithfulness checks."
        ],
        "mlops": [
            "Add model registry simulation and drift trend charts.",
            "Add deployment risk scoring before production release."
        ],
        "data_engineering": [
            "Add data lineage graph and pipeline dependency impact analysis.",
            "Add data contract validation for schema changes."
        ],
        "cybersecurity": [
            "Add severity-weighted vulnerability prioritization.",
            "Add MITRE-style tactic mapping for security signals."
        ],
        "computer_vision": [
            "Add batch image evaluation and false-positive review workflow.",
            "Add annotation feedback for improving detections."
        ],
        "fintech": [
            "Add explainable fraud/risk reason codes.",
            "Add threshold tuning for false positives and false negatives."
        ],
        "developer_tools": [
            "Add GitHub API integration for repository metrics.",
            "Add pull-request risk scoring and technical debt trend tracking."
        ],
        "cloud": [
            "Add monthly cost trend forecasting.",
            "Add resource cleanup recommendations with estimated savings."
        ],
        "devops": [
            "Add flaky-test detection and incident timeline generation.",
            "Add deployment risk prediction from past pipeline failures."
        ]
    }

    features.extend(domain_features.get(domain, []))

    return features


def build_tech_stack_from_blueprint(blueprint: Dict) -> List[str]:
    domain = normalize_domain(blueprint.get("detected_domain", "general"))
    skills = blueprint.get("skills", [])

    base_stack = ["Python", "FastAPI", "Streamlit", "PostgreSQL", "Docker"]

    domain_stack = {
        "frontend": ["React", "TypeScript", "Tailwind CSS", "Vite", "Playwright"],
        "backend": ["FastAPI", "PostgreSQL", "Redis", "Docker", "OpenAPI"],
        "full_stack": ["React", "TypeScript", "FastAPI", "PostgreSQL", "Docker"],
        "rag_llm": ["Sentence Transformers", "FAISS", "LangChain / LlamaIndex", "RAG Evaluation", "Vector Search"],
        "ai_ml": ["scikit-learn", "Pandas", "Model Evaluation", "Explainability"],
        "mlops": ["MLflow Concepts", "Model Registry", "Drift Detection", "CI/CD"],
        "data_engineering": ["SQL", "Pandas", "Data Validation", "Airflow Concepts"],
        "databases": ["PostgreSQL", "SQL", "Indexing", "Query Plans"],
        "cloud": ["AWS Concepts", "CloudWatch-style Metrics", "Cost Analysis"],
        "devops": ["GitHub Actions", "Docker", "Logs", "Monitoring"],
        "cybersecurity": ["Security Logs", "Risk Scoring", "Threat Modeling"],
        "blockchain": ["Solidity Concepts", "Ethereum", "Transaction Analysis"],
        "healthcare_ai": ["Healthcare Analytics", "NLP", "Risk Scoring"],
        "mobile": ["React Native", "Mobile UI", "Offline Sync"],
        "education_tech": ["Learning Analytics", "Recommendation Logic"],
        "recommendation_systems": ["Ranking", "Collaborative Filtering Concepts", "Personalization"],
        "nlp": ["NLP", "Text Classification", "Summarization"],
        "computer_vision": ["OpenCV Concepts", "OCR", "Object Detection", "Image Processing"],
        "fintech": ["Fraud Detection", "Financial Analytics", "Risk Scoring"],
        "developer_tools": ["GitHub APIs", "Code Analysis", "Automation"]
    }

    stack = base_stack + domain_stack.get(domain, []) + skills

    deduped = []
    for item in stack:
        if item and item not in deduped:
            deduped.append(item)

    return deduped[:12]


def build_target_roles_from_blueprint(blueprint: Dict) -> List[str]:
    domain = normalize_domain(blueprint.get("detected_domain", "general"))
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])
    return profile["roles"][:4]


def normalize_domain(domain: str) -> str:
    if not domain:
        return "general"

    domain = str(domain).lower().strip()
    return DOMAIN_ALIASES.get(domain, domain)
