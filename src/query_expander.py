import re
from typing import Dict, List


DOMAIN_KEYWORDS = {
    "rag_llm": [
        "rag",
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "llm",
        "large language model",
        "langchain",
        "llamaindex",
        "vector database",
        "vector search",
        "semantic search",
        "embeddings",
        "hallucination",
        "faithfulness",
        "prompt",
        "question answering",
        "qa system",
        "chatbot",
        "agent"
    ],
    "mlops": [
        "mlops",
        "model registry",
        "experiment tracking",
        "model monitoring",
        "model deployment",
        "model drift",
        "feature store",
        "ml pipeline",
        "training pipeline",
        "inference pipeline"
    ],
    "data_engineering": [
        "data engineering",
        "data pipeline",
        "etl",
        "elt",
        "airflow",
        "dbt",
        "spark",
        "kafka",
        "data warehouse",
        "data lake",
        "data quality",
        "schema drift",
        "batch processing",
        "stream processing"
    ],
    "cloud": [
        "cloud",
        "aws",
        "azure",
        "gcp",
        "cloud cost",
        "cost optimization",
        "finops",
        "serverless",
        "lambda",
        "s3",
        "ec2",
        "cloud monitoring",
        "cloud deployment"
    ],
    "devops": [
        "devops",
        "ci/cd",
        "cicd",
        "github actions",
        "jenkins",
        "docker",
        "kubernetes",
        "terraform",
        "deployment",
        "observability",
        "infrastructure",
        "logs",
        "monitoring"
    ],
    "cybersecurity": [
        "cybersecurity",
        "cyber security",
        "security",
        "vulnerability",
        "threat",
        "malware",
        "phishing",
        "zero day",
        "zeroday",
        "incident response",
        "soc",
        "siem",
        "risk scoring",
        "exploit",
        "authentication",
        "authorization"
    ],
    "healthcare_ai": [
        "healthcare",
        "health care",
        "medical",
        "clinical",
        "ehr",
        "patient",
        "hospital",
        "diagnosis",
        "appointment",
        "medication",
        "biomedical"
    ],
    "blockchain": [
        "blockchain",
        "smart contract",
        "solidity",
        "ethereum",
        "web3",
        "defi",
        "nft",
        "crypto wallet",
        "dao"
    ],
    "frontend": [
        "frontend",
        "front end",
        "front-end",
        "react",
        "next.js",
        "nextjs",
        "vue",
        "angular",
        "typescript",
        "tailwind",
        "ui",
        "ux",
        "component",
        "design system",
        "web app"
    ],
    "backend": [
        "backend",
        "back end",
        "back-end",
        "api",
        "rest api",
        "graphql",
        "microservice",
        "fastapi",
        "django",
        "flask",
        "spring boot",
        "node.js",
        "express",
        "service architecture"
    ],
    "databases": [
        "database",
        "databases",
        "sql",
        "postgres",
        "postgresql",
        "mysql",
        "mongodb",
        "redis",
        "query optimization",
        "indexing",
        "transactions"
    ],
    "mobile": [
        "mobile",
        "android",
        "ios",
        "react native",
        "flutter",
        "swift",
        "kotlin",
        "mobile app"
    ],
    "computer_vision": [
        "computer vision",
        "image recognition",
        "object detection",
        "ocr",
        "segmentation",
        "opencv",
        "vision transformer"
    ],
    "nlp": [
        "nlp",
        "natural language processing",
        "text classification",
        "named entity",
        "sentiment",
        "summarization",
        "text mining"
    ],
    "recommendation_systems": [
        "recommendation",
        "recommendation system",
        "recommender",
        "personalization",
        "ranking",
        "collaborative filtering"
    ],
    "education_tech": [
        "education",
        "edtech",
        "student",
        "learning",
        "course",
        "tutor",
        "learning path"
    ],
    "fintech": [
        "fintech",
        "finance",
        "trading",
        "fraud detection",
        "payment",
        "banking",
        "credit risk"
    ],
    "developer_tools": [
        "developer tool",
        "developer tools",
        "code analysis",
        "code review",
        "debugger",
        "debugging",
        "repository",
        "github",
        "cli tool"
    ],
    "ai_ml": [
        "ai",
        "machine learning",
        "deep learning",
        "classification",
        "prediction",
        "forecasting",
        "neural network",
        "model training"
    ],
    "full_stack": [
        "full stack",
        "full-stack",
        "saas",
        "dashboard app",
        "web platform",
        "end to end",
        "end-to-end"
    ]
}


PROJECT_INTENT_KEYWORDS = [
    "project",
    "projects",
    "build",
    "make",
    "create",
    "prototype",
    "mvp",
    "app",
    "tool",
    "platform",
    "dashboard",
    "portfolio",
    "github",
    "resume"
]


RESEARCH_INTENT_KEYWORDS = [
    "research",
    "paper",
    "papers",
    "survey",
    "literature",
    "method",
    "methods",
    "benchmark",
    "evaluation",
    "architecture",
    "algorithm",
    "dataset"
]


def clean_query(query: str) -> str:
    query = query or ""
    query = query.strip()
    query = re.sub(r"\s+", " ", query)
    return query


def detect_domain(query: str) -> str:
    cleaned_query = clean_query(query).lower()

    if not cleaned_query:
        return "general"

    best_domain = "general"
    best_score = 0

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0

        for keyword in keywords:
            keyword = keyword.lower()

            if keyword in cleaned_query:
                if " " in keyword or "-" in keyword:
                    score += 3
                else:
                    score += 1

        if score > best_score:
            best_score = score
            best_domain = domain

    return best_domain


def detect_intent(query: str) -> str:
    cleaned_query = clean_query(query).lower()

    has_project_intent = any(
        keyword in cleaned_query
        for keyword in PROJECT_INTENT_KEYWORDS
    )

    has_research_intent = any(
        keyword in cleaned_query
        for keyword in RESEARCH_INTENT_KEYWORDS
    )

    if has_project_intent and has_research_intent:
        return "research_backed_project"

    if has_project_intent:
        return "project_building"

    if has_research_intent:
        return "research_exploration"

    return "general"


def get_known_topic_expansion(query: str) -> str:
    domain = detect_domain(query)

    expansions = {
        "rag_llm": "retrieval augmented generation semantic search vector database embeddings hallucination faithfulness LLM evaluation citations question answering",
        "mlops": "MLOps experiment tracking model registry model monitoring drift detection deployment inference pipeline",
        "data_engineering": "data pipelines ETL ELT Airflow dbt Spark Kafka data quality schema drift warehouse lakehouse",
        "cloud": "cloud architecture AWS Azure GCP cost optimization FinOps serverless monitoring deployment infrastructure",
        "devops": "CI/CD Docker Kubernetes Terraform observability logs deployment automation developer productivity",
        "cybersecurity": "cybersecurity vulnerability risk scoring threat detection incident response zero trust exploit prioritization",
        "healthcare_ai": "healthcare AI clinical data EHR patient analytics medical NLP prediction operational healthcare intelligence",
        "blockchain": "blockchain smart contracts Solidity Ethereum Web3 DeFi security risk analysis decentralized applications",
        "frontend": "React TypeScript frontend architecture UI UX component design system accessibility performance",
        "backend": "backend APIs microservices FastAPI Node.js PostgreSQL service architecture observability system design",
        "databases": "SQL PostgreSQL indexing query optimization transactions database performance schema design",
        "mobile": "mobile app React Native Flutter Android iOS mobile UI offline sync notifications",
        "computer_vision": "computer vision image recognition object detection OCR segmentation OpenCV vision transformer",
        "nlp": "natural language processing text classification summarization entity extraction information retrieval",
        "recommendation_systems": "recommendation systems personalization ranking collaborative filtering content-based filtering user modeling",
        "education_tech": "education technology learning paths tutoring skill assessment student progress personalized learning",
        "fintech": "fintech fraud detection credit risk payment analytics financial data risk scoring",
        "developer_tools": "developer tools code analysis debugging repository intelligence CI automation engineering productivity",
        "ai_ml": "machine learning prediction classification deep learning model evaluation feature engineering AI applications",
        "full_stack": "full stack web platform frontend backend database authentication deployment dashboard"
    }

    return expansions.get(domain, "")


def get_generic_fallback_expansion(domain: str, intent: str) -> str:
    base = DOMAIN_KEYWORDS.get(domain, [])
    base_text = " ".join(base[:10])

    if intent in ["project_building", "research_backed_project"]:
        return f"{base_text} project ideas MVP roadmap technical skills target roles implementation"

    if intent == "research_exploration":
        return f"{base_text} research papers methods datasets benchmarks evaluation"

    return base_text


def expand_query(user_query: str) -> str:
    cleaned_query = clean_query(user_query)
    domain = detect_domain(cleaned_query)
    intent = detect_intent(cleaned_query)

    known_expansion = get_known_topic_expansion(cleaned_query)
    fallback_expansion = get_generic_fallback_expansion(domain, intent)

    expansion_parts = [
        cleaned_query,
        known_expansion,
        fallback_expansion
    ]

    expanded_query = " ".join(
        part for part in expansion_parts
        if part
    )

    return re.sub(r"\s+", " ", expanded_query).strip()


def get_query_metadata(user_query: str) -> Dict:
    cleaned_query = clean_query(user_query)
    detected_domain = detect_domain(cleaned_query)
    detected_intent = detect_intent(cleaned_query)
    expanded_query = expand_query(cleaned_query)

    return {
        "original_query": user_query,
        "cleaned_query": cleaned_query,
        "expanded_query": expanded_query,
        "detected_domain": detected_domain,
        "detected_intent": detected_intent
    }
