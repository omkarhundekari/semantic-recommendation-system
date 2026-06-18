import os
import pandas as pd


OUTPUT_PATH = "data/project_corpus.csv"


COLUMNS = [
    "title",
    "content",
    "category",
    "source_type",
    "url",
    "tags",
    "difficulty",
    "target_roles",
    "skills",
    "project_type",
    "freshness"
]


PROJECT_PATTERNS = [
    # Frontend
    ("AI-Powered Frontend Project Generator", "frontend", "medium", "Frontend Engineer, Full-Stack Engineer, UI Engineer", "React, TypeScript, Tailwind CSS, UI Architecture, Project Planning", "react,typescript,tailwind,frontend,portfolio,ui,project-planning", "portfolio_intelligence"),
    ("Reusable Component Discovery Dashboard", "frontend", "medium", "Frontend Engineer, Design Systems Engineer, Full-Stack Engineer", "React, TypeScript, Component Architecture, Design Systems", "react,components,design-system,typescript,frontend", "developer_tool"),
    ("Frontend Performance and UX Intelligence Platform", "frontend", "medium", "Frontend Engineer, Web Performance Engineer, Full-Stack Engineer", "React, Performance Optimization, Accessibility, Analytics", "frontend,performance,accessibility,core-web-vitals,ux", "analysis_tool"),
    ("React Architecture Recommendation Engine", "frontend", "medium", "Frontend Engineer, Full-Stack Engineer, UI Engineer", "React, TypeScript, State Management, Testing, Architecture", "react,architecture,state-management,testing,frontend", "architecture_advisor"),
    ("Design System Governance Assistant", "frontend", "medium", "Frontend Engineer, Design Systems Engineer, UI Engineer", "Design Systems, Component APIs, Documentation, Accessibility", "design-system,components,frontend,accessibility,documentation", "developer_tool"),
    ("Accessibility Audit and Fix Recommendation Tool", "frontend", "medium", "Frontend Engineer, Accessibility Engineer, Full-Stack Engineer", "Accessibility, WCAG, React, UI Testing, Reports", "accessibility,wcag,frontend,react,testing", "analysis_tool"),
    ("Frontend Test Coverage Intelligence Dashboard", "frontend", "medium", "Frontend Engineer, QA Automation Engineer, Full-Stack Engineer", "React Testing Library, Playwright, Test Analytics, TypeScript", "frontend,testing,playwright,coverage,typescript", "developer_tool"),

    # Backend
    ("Backend API Monitoring Platform", "backend", "medium", "Backend Engineer, Platform Engineer, Full-Stack Engineer", "FastAPI, PostgreSQL, Docker, API Design, Observability", "backend,api,observability,fastapi,postgresql,docker", "observability_tool"),
    ("Microservice Dependency Mapper", "backend", "high", "Backend Engineer, Platform Engineer, Site Reliability Engineer", "System Design, APIs, Graph Modeling, Observability", "backend,microservices,dependency-graph,system-design,observability", "system_intelligence"),
    ("API Contract Testing and Drift Detector", "backend", "medium", "Backend Engineer, Platform Engineer, QA Automation Engineer", "OpenAPI, Contract Testing, FastAPI, CI/CD", "api,contract-testing,openapi,backend,ci-cd", "developer_tool"),
    ("Event-Driven Order Processing Simulator", "backend", "high", "Backend Engineer, Distributed Systems Engineer, Platform Engineer", "Message Queues, Event-Driven Architecture, PostgreSQL, Docker", "backend,event-driven,kafka,queues,system-design", "simulation_platform"),
    ("Multi-Tenant SaaS Backend Starter Platform", "backend", "high", "Backend Engineer, Full-Stack Engineer, SaaS Engineer", "Authentication, Authorization, PostgreSQL, APIs, System Design", "backend,saas,multi-tenant,auth,postgresql", "saas_platform"),
    ("Rate Limiting and Abuse Detection API Gateway", "backend", "high", "Backend Engineer, Security Engineer, Platform Engineer", "API Gateway, Redis, Rate Limiting, Abuse Detection", "backend,api-gateway,redis,security,rate-limiting", "security_tool"),

    # Full stack
    ("Personal Knowledge Base RAG App", "full_stack", "high", "Full-Stack Engineer, AI Engineer, Backend Engineer", "RAG, Full-Stack Development, File Processing, Semantic Search", "full-stack,rag,documents,pdf,semantic-search,citations", "ai_productivity"),
    ("AI-Powered Job Application Tracker", "full_stack", "medium", "Full-Stack Engineer, Product Engineer, Backend Engineer", "React, FastAPI, PostgreSQL, Automation, Analytics", "full-stack,job-tracker,automation,analytics,postgresql", "productivity_tool"),
    ("Collaborative Project Roadmap Builder", "full_stack", "medium", "Full-Stack Engineer, Product Engineer, Frontend Engineer", "React, APIs, Collaboration, Roadmaps, Dashboards", "full-stack,roadmap,collaboration,project-management", "productivity_tool"),
    ("Resume-to-Project Recommendation Platform", "full_stack", "high", "Full-Stack Engineer, AI Engineer, Career Tech Engineer", "NLP, Skill Extraction, Recommendations, Full-Stack", "resume,projects,recommendation,skills,career,full-stack", "career_intelligence"),

    # RAG / LLM
    ("RAG Evaluation Dashboard", "rag_llm", "high", "AI Engineer, LLM Application Engineer, NLP Engineer", "RAG, Semantic Search, Vector Search, LLM Evaluation, Python", "rag,llm,evaluation,semantic-search,faithfulness,hallucination", "ai_evaluation"),
    ("Research Paper RAG Assistant", "rag_llm", "high", "AI Engineer, NLP Engineer, Research Engineer", "RAG, Embeddings, FAISS, NLP, Streamlit", "rag,research-papers,semantic-search,citations,question-answering", "research_copilot"),
    ("RAG Pipeline Debugger", "rag_llm", "high", "AI Engineer, LLM Engineer, Developer Tools Engineer", "RAG, LLM Debugging, Evaluation, Vector Search", "rag,debugging,chunking,retrieval,evaluation,developer-tools", "developer_tool"),
    ("Hallucination Risk Scoring System", "rag_llm", "high", "AI Engineer, LLM Evaluation Engineer, NLP Engineer", "LLM Evaluation, Faithfulness, Citation Checking, RAG", "llm,hallucination,faithfulness,evaluation,citations,rag", "ai_evaluation"),
    ("Prompt Versioning and Evaluation Platform", "rag_llm", "medium", "AI Engineer, LLM Application Engineer, Developer Tools Engineer", "Prompt Engineering, Evaluation, Versioning, Experiment Tracking", "prompt-engineering,llm,evaluation,versioning,experiments", "developer_tool"),
    ("Multi-Agent Research Planning Assistant", "rag_llm", "high", "AI Engineer, Research Engineer, LLM Application Engineer", "Agents, RAG, Planning, Tool Use, Evaluation", "agents,rag,research,planning,llm,tool-use", "research_copilot"),
    ("Document Chunking Strategy Analyzer", "rag_llm", "medium", "AI Engineer, NLP Engineer, Search Engineer", "Chunking, Embeddings, Retrieval Evaluation, Semantic Search", "chunking,embeddings,retrieval,rag,semantic-search", "analysis_tool"),
    ("Citation Coverage Checker for LLM Answers", "rag_llm", "medium", "AI Engineer, NLP Engineer, LLM Evaluation Engineer", "Citations, RAG, Answer Grounding, Evaluation", "citations,answer-grounding,rag,llm,evaluation", "ai_evaluation"),

    # AI / ML
    ("Machine Learning Model Comparison Dashboard", "ai_ml", "medium", "ML Engineer, Data Scientist, AI Engineer", "Model Evaluation, Metrics, Python, Dashboards", "machine-learning,model-evaluation,metrics,dashboard", "ml_dashboard"),
    ("AutoML Experiment Recommendation Assistant", "ai_ml", "high", "ML Engineer, Data Scientist, AI Engineer", "AutoML, Feature Engineering, Model Selection, Evaluation", "automl,feature-engineering,model-selection,ml", "ml_assistant"),
    ("Anomaly Detection for Business Operations", "ai_ml", "medium", "ML Engineer, Data Analyst, Backend Engineer", "Anomaly Detection, Time Series, Dashboards, Python", "anomaly-detection,time-series,operations,analytics", "predictive_analytics"),
    ("Forecasting Model Monitoring Dashboard", "ai_ml", "medium", "ML Engineer, Data Scientist, MLOps Engineer", "Forecasting, Model Monitoring, Drift Detection, Metrics", "forecasting,model-monitoring,drift,ml", "ml_monitoring"),
    ("Feature Importance Explanation Tool", "ai_ml", "medium", "ML Engineer, Data Scientist, AI Engineer", "Explainability, Feature Importance, Model Interpretation", "explainability,feature-importance,ml,interpretability", "analysis_tool"),

    # MLOps
    ("MLOps Experiment Tracking Platform", "mlops", "high", "ML Engineer, MLOps Engineer, Data Scientist", "Experiment Tracking, Model Registry, Metrics, ML Pipelines", "mlops,experiment-tracking,model-registry,metrics", "mlops_platform"),
    ("Model Drift Detection Dashboard", "mlops", "high", "MLOps Engineer, ML Engineer, Data Engineer", "Drift Detection, Monitoring, Feature Statistics, Alerts", "mlops,drift-detection,model-monitoring,alerts", "mlops_monitoring"),
    ("Model Deployment Readiness Checker", "mlops", "medium", "MLOps Engineer, ML Engineer, Platform Engineer", "Deployment, Validation, Model Cards, CI/CD", "mlops,deployment,validation,model-cards,ci-cd", "developer_tool"),
    ("Feature Store Usage Analyzer", "mlops", "high", "MLOps Engineer, Data Engineer, ML Engineer", "Feature Stores, Data Quality, Lineage, Monitoring", "feature-store,mlops,data-quality,lineage", "data_platform"),
    ("Inference Latency Monitoring Platform", "mlops", "high", "MLOps Engineer, Platform Engineer, ML Engineer", "Inference Monitoring, Latency, APIs, Observability", "inference,latency,mlops,observability,api", "observability_tool"),

    # Data engineering
    ("Data Pipeline Quality Monitor", "data_engineering", "medium", "Data Engineer, Analytics Engineer, Backend Engineer", "Python, SQL, Data Validation, ETL, Monitoring", "data-engineering,pipelines,data-quality,etl,monitoring", "data_quality_tool"),
    ("Schema Drift Detection Platform", "data_engineering", "medium", "Data Engineer, Analytics Engineer, Backend Engineer", "Schema Validation, Data Contracts, SQL, Alerts", "schema-drift,data-contracts,data-quality,pipelines", "data_quality_tool"),
    ("ETL Pipeline Dependency Visualizer", "data_engineering", "medium", "Data Engineer, Analytics Engineer, Platform Engineer", "ETL, DAGs, Airflow Concepts, Visualization", "etl,airflow,dags,data-pipelines,visualization", "developer_tool"),
    ("Streaming Data Anomaly Monitor", "data_engineering", "high", "Data Engineer, Streaming Engineer, ML Engineer", "Kafka Concepts, Streaming, Anomaly Detection, Monitoring", "streaming,kafka,anomaly-detection,data-engineering", "streaming_platform"),
    ("Data Warehouse Cost and Query Analyzer", "data_engineering", "medium", "Data Engineer, Analytics Engineer, Database Engineer", "SQL, Query Analytics, Cost Optimization, Dashboards", "warehouse,sql,cost,query-analysis,data-engineering", "analysis_tool"),

    # Databases
    ("Database Query Optimization Assistant", "databases", "medium", "Backend Engineer, Database Engineer, Data Engineer", "SQL, PostgreSQL, Query Optimization, Indexing", "sql,postgresql,indexing,query-optimization,database", "developer_tool"),
    ("PostgreSQL Index Recommendation Tool", "databases", "medium", "Database Engineer, Backend Engineer, Data Engineer", "PostgreSQL, Indexing, Query Plans, SQL", "postgresql,indexing,query-plans,sql,database", "developer_tool"),
    ("Database Migration Risk Analyzer", "databases", "medium", "Database Engineer, Backend Engineer, Platform Engineer", "Schema Migration, SQL, Risk Analysis, Testing", "database,migration,schema,risk-analysis,testing", "analysis_tool"),
    ("Redis Cache Effectiveness Dashboard", "databases", "medium", "Backend Engineer, Platform Engineer, Database Engineer", "Redis, Caching, Metrics, Backend Performance", "redis,caching,database,performance,backend", "observability_tool"),

    # Cloud
    ("Cloud Cost Optimization Dashboard", "cloud", "medium", "Cloud Engineer, DevOps Engineer, Platform Engineer", "Cloud Monitoring, AWS Concepts, Dashboards, Cost Analysis", "cloud,cost-optimization,aws,monitoring,finops", "cloud_dashboard"),
    ("Serverless Function Observability Tool", "cloud", "medium", "Cloud Engineer, Backend Engineer, DevOps Engineer", "Serverless, Logs, Monitoring, AWS Lambda Concepts", "serverless,lambda,cloud,observability,logs", "observability_tool"),
    ("Cloud Resource Cleanup Recommender", "cloud", "medium", "Cloud Engineer, DevOps Engineer, Platform Engineer", "Cloud Inventory, Cost Analysis, Automation, Dashboards", "cloud,resource-cleanup,cost,automation,finops", "cloud_dashboard"),
    ("Multi-Cloud Deployment Comparison Dashboard", "cloud", "high", "Cloud Engineer, Platform Engineer, DevOps Engineer", "AWS, Azure, GCP Concepts, Deployment, Cost Analysis", "multi-cloud,aws,azure,gcp,deployment,cost", "analysis_tool"),
    ("Infrastructure Risk and Misconfiguration Scanner", "cloud", "high", "Cloud Engineer, Security Engineer, DevOps Engineer", "Cloud Security, Misconfiguration Detection, Risk Scoring", "cloud,security,misconfiguration,risk-scoring", "security_tool"),

    # DevOps
    ("CI/CD Failure Intelligence Platform", "devops", "medium", "DevOps Engineer, Platform Engineer, Software Engineer", "CI/CD, Logs, GitHub Actions, Testing, Automation", "devops,ci-cd,github-actions,testing,logs", "developer_tool"),
    ("Flaky Test Detection Dashboard", "devops", "medium", "DevOps Engineer, QA Automation Engineer, Platform Engineer", "Testing, CI/CD, Log Analysis, Reliability", "flaky-tests,testing,ci-cd,devops,reliability", "developer_tool"),
    ("Deployment Risk Scoring System", "devops", "high", "DevOps Engineer, Platform Engineer, Site Reliability Engineer", "Deployment, Risk Scoring, CI/CD, Observability", "deployment,risk-scoring,ci-cd,devops,observability", "observability_tool"),
    ("Kubernetes Resource Recommendation Dashboard", "devops", "high", "DevOps Engineer, Platform Engineer, Cloud Engineer", "Kubernetes, Resource Optimization, Monitoring", "kubernetes,resources,optimization,monitoring,devops", "cloud_dashboard"),
    ("Incident Postmortem Generator", "devops", "medium", "SRE, DevOps Engineer, Platform Engineer", "Incident Analysis, Logs, Summarization, Reliability", "incident,postmortem,logs,sre,devops", "developer_tool"),

    # Cybersecurity
    ("Security Vulnerability Prioritization Engine", "cybersecurity", "high", "Security Engineer, Backend Engineer, Platform Engineer", "Security Risk Scoring, APIs, Databases, Threat Modeling", "security,vulnerability,cvss,risk-scoring,prioritization", "security_tool"),
    ("Phishing Email Detection Dashboard", "cybersecurity", "medium", "Security Engineer, ML Engineer, Backend Engineer", "NLP, Classification, Security Analytics, Dashboards", "phishing,email-security,nlp,classification,cybersecurity", "security_tool"),
    ("Zero Trust Access Policy Analyzer", "cybersecurity", "high", "Security Engineer, Platform Engineer, Cloud Engineer", "Zero Trust, Access Control, Policy Analysis, Risk Scoring", "zero-trust,access-control,policy,security", "security_tool"),
    ("Security Log Anomaly Detector", "cybersecurity", "high", "Security Engineer, Data Engineer, ML Engineer", "Log Analysis, Anomaly Detection, Security Monitoring", "security,logs,anomaly-detection,siem,monitoring", "security_tool"),
    ("Dependency Vulnerability Intelligence Tool", "cybersecurity", "medium", "Security Engineer, Software Engineer, DevSecOps Engineer", "Dependency Scanning, CVE Analysis, Risk Prioritization", "dependencies,cve,security,devsecops,vulnerability", "developer_tool"),

    # Blockchain
    ("Smart Contract Risk Analyzer", "blockchain", "high", "Blockchain Engineer, Security Engineer, Backend Engineer", "Solidity Concepts, Security Analysis, Risk Scoring", "blockchain,smart-contracts,security,ethereum,solidity", "security_tool"),
    ("DeFi Transaction Risk Dashboard", "blockchain", "high", "Blockchain Engineer, Data Engineer, Security Engineer", "Blockchain Analytics, Risk Scoring, Transaction Graphs", "defi,transactions,blockchain,risk,analytics", "analysis_tool"),
    ("DAO Governance Analytics Platform", "blockchain", "medium", "Blockchain Engineer, Data Analyst, Full-Stack Engineer", "Governance, Voting Analytics, Dashboards, Web3", "dao,governance,voting,web3,analytics", "analysis_tool"),

    # Healthcare AI
    ("Healthcare Appointment No-Show Predictor", "healthcare_ai", "medium", "Data Scientist, ML Engineer, Healthcare Data Analyst", "Machine Learning, Data Analysis, Feature Engineering, Dashboards", "healthcare,machine-learning,prediction,analytics,appointments", "predictive_analytics"),
    ("Clinical Notes Summarization Assistant", "healthcare_ai", "high", "AI Engineer, NLP Engineer, Healthcare Data Engineer", "NLP, Summarization, Healthcare Text, Evaluation", "healthcare,nlp,summarization,clinical-notes", "ai_assistant"),
    ("Medication Interaction Risk Checker", "healthcare_ai", "high", "Healthcare AI Engineer, Backend Engineer, Data Engineer", "Knowledge Graphs, Risk Scoring, Healthcare Data", "healthcare,medication,risk,knowledge-graph,clinical", "healthcare_tool"),
    ("Patient Readmission Risk Dashboard", "healthcare_ai", "high", "ML Engineer, Data Scientist, Healthcare Analyst", "Predictive Modeling, Healthcare Analytics, Dashboards", "healthcare,readmission,prediction,analytics,ml", "predictive_analytics"),
    ("Healthcare Document RAG Assistant", "healthcare_ai", "high", "AI Engineer, Healthcare Data Engineer, NLP Engineer", "RAG, Healthcare Documents, Citations, Semantic Search", "healthcare,rag,documents,citations,semantic-search", "research_copilot"),

    # Mobile
    ("Mobile Habit Tracker with AI Insights", "mobile", "medium", "Mobile Engineer, Full-Stack Engineer, Product Engineer", "React Native, Mobile UI, Analytics, Personalization", "mobile,react-native,habit-tracking,analytics", "mobile_app"),
    ("Offline-First Notes App with Sync Intelligence", "mobile", "medium", "Mobile Engineer, Full-Stack Engineer", "Offline Sync, Mobile Storage, Conflict Resolution", "mobile,offline-first,sync,notes,conflict-resolution", "mobile_app"),
    ("Mobile Expense Tracker with Fraud Alerts", "mobile", "medium", "Mobile Engineer, FinTech Engineer, Full-Stack Engineer", "Mobile UI, Analytics, Alerts, Personal Finance", "mobile,expense-tracking,fraud-alerts,fintech", "mobile_app"),

    # Education tech
    ("Student Learning Path Recommendation System", "education_tech", "medium", "Full-Stack Engineer, AI Engineer, EdTech Developer", "Recommendation Systems, Skill Mapping, Backend APIs, Dashboards", "education,recommendation,learning-paths,skills,career", "recommendation_system"),
    ("AI Tutor Progress Analytics Dashboard", "education_tech", "medium", "AI Engineer, Full-Stack Engineer, EdTech Engineer", "Learning Analytics, Dashboards, NLP, Personalization", "education,ai-tutor,analytics,personalization", "education_platform"),
    ("Course Difficulty Prediction Tool", "education_tech", "medium", "Data Scientist, Full-Stack Engineer, EdTech Developer", "Prediction, Student Data, Analytics, Dashboards", "education,prediction,course-difficulty,analytics", "predictive_analytics"),

    # Recommendation systems
    ("Movie Recommendation System with Explanation Layer", "recommendation_systems", "medium", "ML Engineer, Backend Engineer, Data Scientist", "Recommendation Systems, Explainability, Ranking", "recommendation,explainability,ranking,movies", "recommendation_system"),
    ("E-Commerce Personalization Engine", "recommendation_systems", "high", "ML Engineer, Backend Engineer, Search Engineer", "Personalization, Ranking, User Modeling, APIs", "ecommerce,personalization,recommendation,ranking", "recommendation_system"),
    ("Career Path Recommendation Engine", "recommendation_systems", "medium", "AI Engineer, Full-Stack Engineer, Data Scientist", "Skill Mapping, Recommendations, Career Intelligence", "career,recommendation,skills,roles,personalization", "career_intelligence"),

    # NLP
    ("Customer Support Ticket Classifier", "nlp", "medium", "NLP Engineer, Backend Engineer, Data Scientist", "Text Classification, NLP, APIs, Dashboards", "nlp,text-classification,support,tickets", "nlp_tool"),
    ("Meeting Transcript Action Item Extractor", "nlp", "medium", "NLP Engineer, Full-Stack Engineer, AI Engineer", "Information Extraction, Summarization, NLP", "nlp,transcripts,action-items,summarization", "productivity_tool"),
    ("Legal Document Clause Analyzer", "nlp", "high", "NLP Engineer, AI Engineer, LegalTech Engineer", "NLP, Document Analysis, Risk Scoring, Summarization", "nlp,legal-documents,clause-analysis,risk", "analysis_tool"),

    # Computer vision
    ("Retail Shelf Object Detection Dashboard", "computer_vision", "high", "Computer Vision Engineer, ML Engineer, Data Scientist", "Object Detection, Image Analytics, Dashboards", "computer-vision,object-detection,retail,analytics", "vision_dashboard"),
    ("OCR Receipt Intelligence App", "computer_vision", "medium", "Computer Vision Engineer, Full-Stack Engineer, Data Engineer", "OCR, Document Processing, Data Extraction", "ocr,receipts,computer-vision,document-processing", "document_ai"),
    ("Construction Site Safety Detection System", "computer_vision", "high", "Computer Vision Engineer, ML Engineer, Safety Tech Engineer", "Object Detection, Safety Analytics, Computer Vision", "computer-vision,safety,object-detection,construction", "vision_system"),

    # Fintech
    ("Fraud Transaction Risk Scoring Dashboard", "fintech", "high", "ML Engineer, FinTech Engineer, Data Scientist", "Fraud Detection, Risk Scoring, Analytics", "fintech,fraud-detection,risk-scoring,transactions", "security_tool"),
    ("Credit Risk Explanation Platform", "fintech", "high", "Data Scientist, ML Engineer, FinTech Engineer", "Credit Risk, Explainability, Model Evaluation", "fintech,credit-risk,explainability,ml", "predictive_analytics"),
    ("Subscription Spend Analyzer", "fintech", "medium", "Full-Stack Engineer, FinTech Engineer, Product Engineer", "Financial Analytics, Dashboards, Categorization", "fintech,subscriptions,spend-analysis,dashboard", "finance_tool"),

    # Developer tools
    ("Repository Health Analyzer", "developer_tools", "medium", "Developer Tools Engineer, Software Engineer, Platform Engineer", "GitHub APIs, Code Metrics, Dashboards, Automation", "developer-tools,github,repository,code-quality", "developer_tool"),
    ("Code Review Risk Assistant", "developer_tools", "high", "Developer Tools Engineer, Backend Engineer, AI Engineer", "Code Analysis, Risk Scoring, Pull Request Intelligence", "code-review,developer-tools,risk,github", "developer_tool"),
    ("Technical Debt Prioritization Dashboard", "developer_tools", "medium", "Developer Tools Engineer, Software Engineer, Engineering Productivity Engineer", "Code Metrics, Prioritization, Dashboards", "technical-debt,developer-tools,code-quality", "developer_tool"),
    ("Architecture Decision Record Generator", "developer_tools", "medium", "Software Engineer, Platform Engineer, Developer Tools Engineer", "System Design, Documentation, Architecture Decisions", "architecture,documentation,adr,developer-tools", "developer_tool"),
]


def build_content(title, category, difficulty, skills, tags, project_type):
    readable_category = category.replace("_", " ")
    readable_type = project_type.replace("_", " ")

    return (
        f"{title} is a {difficulty} {readable_category} project pattern for building a "
        f"{readable_type}. It focuses on practical implementation, evidence-grounded planning, "
        f"role-aligned technical depth, and portfolio-ready output. Core skills include {skills}. "
        f"The project is relevant to modern topics such as {tags}."
    )


def build_project_corpus():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    rows = []

    for title, category, difficulty, target_roles, skills, tags, project_type in PROJECT_PATTERNS:
        rows.append({
            "title": title,
            "content": build_content(
                title=title,
                category=category,
                difficulty=difficulty,
                skills=skills,
                tags=tags,
                project_type=project_type
            ),
            "category": category,
            "source_type": "project_pattern",
            "url": "",
            "tags": tags,
            "difficulty": difficulty,
            "target_roles": target_roles,
            "skills": skills,
            "project_type": project_type,
            "freshness": "modern"
        })

    df = pd.DataFrame(rows)
    df = df[COLUMNS]

    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved project corpus to {OUTPUT_PATH}")
    print(f"Rows: {len(df)}")
    print()
    print("Category counts:")
    print(df["category"].value_counts())


if __name__ == "__main__":
    build_project_corpus()
