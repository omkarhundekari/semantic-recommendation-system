import os
import time
import json
from typing import Dict, List

import pandas as pd
import requests


OUTPUT_PATH = "data/github_project_corpus.csv"
STATE_PATH = "data/github_ingestion_state.json"
GITHUB_API_URL = "https://api.github.com/search/repositories"

MAX_RESULTS_PER_QUERY = 5
SLEEP_SECONDS = 1.5


SEARCH_TOPICS = {
    "frontend": [
        "react typescript dashboard",
        "react design system",
        "frontend performance accessibility"
    ],
    "backend": [
        "fastapi backend api",
        "microservices observability",
        "api monitoring platform"
    ],
    "rag_llm": [
        "rag evaluation",
        "retrieval augmented generation",
        "llm evaluation rag"
    ],
    "mlops": [
        "mlops experiment tracking",
        "model monitoring drift detection",
        "ml pipeline monitoring"
    ],
    "data_engineering": [
        "data quality pipeline",
        "etl pipeline monitoring",
        "schema drift detection"
    ],
    "cybersecurity": [
        "vulnerability scanner",
        "security log anomaly detection",
        "phishing detection"
    ],
    "cloud": [
        "cloud cost optimization",
        "aws cost dashboard",
        "cloud resource monitoring"
    ],
    "devops": [
        "ci cd failure analysis",
        "github actions monitoring",
        "deployment risk"
    ],
    "computer_vision": [
        "ocr receipt extraction",
        "object detection dashboard",
        "computer vision safety detection"
    ],
    "fintech": [
        "fraud detection transactions",
        "credit risk machine learning",
        "finance analytics dashboard"
    ],
    "developer_tools": [
        "code review assistant",
        "repository health dashboard",
        "technical debt dashboard"
    ],
    "healthcare_ai": [
        "clinical notes nlp",
        "healthcare machine learning",
        "medical document rag"
    ]
}


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
    "freshness",
    "stars",
    "forks",
    "language",
    "updated_at"
]


# These are the queries that already completed during your first run.
# We seed them once so the script does not waste API requests repeating them.
BOOTSTRAP_COMPLETED_QUERIES = {
    "frontend::react typescript dashboard",
    "frontend::react design system",
    "frontend::frontend performance accessibility",
    "backend::fastapi backend api",
    "backend::microservices observability",
    "backend::api monitoring platform",
    "rag_llm::rag evaluation",
    "rag_llm::retrieval augmented generation",
    "rag_llm::llm evaluation rag",
    "mlops::mlops experiment tracking",
    "mlops::model monitoring drift detection",
    "mlops::ml pipeline monitoring",
    "data_engineering::data quality pipeline",
    "data_engineering::etl pipeline monitoring",
    "data_engineering::schema drift detection",
}


def make_query_key(category: str, query: str) -> str:
    return f"{category}::{query}"


def load_ingestion_state(existing_rows_count: int) -> dict:
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r") as file:
                state = json.load(file)

            state.setdefault("completed_queries", [])
            return state
        except Exception:
            pass

    completed_queries = []

    # Your earlier run already fetched these categories successfully.
    # Only seed this state when a saved GitHub corpus already exists.
    if existing_rows_count > 0:
        completed_queries = sorted(BOOTSTRAP_COMPLETED_QUERIES)

    return {"completed_queries": completed_queries}


def save_ingestion_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)

    with open(STATE_PATH, "w") as file:
        json.dump(state, file, indent=2)



def get_headers() -> Dict[str, str]:
    token = os.getenv("GITHUB_TOKEN")

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def load_existing_rows() -> List[Dict]:
    if not os.path.exists(OUTPUT_PATH):
        return []

    try:
        df = pd.read_csv(OUTPUT_PATH)
        return df.to_dict("records")
    except Exception:
        return []


def save_rows(rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    if not rows:
        return

    df = pd.DataFrame(rows)

    for column in COLUMNS:
        if column not in df.columns:
            df[column] = ""

    df = df[COLUMNS]
    df = df.drop_duplicates(subset=["url"])
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved {len(df)} rows to {OUTPUT_PATH}")


def search_github_repositories(query: str, category: str) -> List[Dict]:
    params = {
        "q": f"{query} stars:>20",
        "sort": "stars",
        "order": "desc",
        "per_page": MAX_RESULTS_PER_QUERY
    }

    response = requests.get(
        GITHUB_API_URL,
        headers=get_headers(),
        params=params,
        timeout=20
    )

    remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
    reset_time = response.headers.get("X-RateLimit-Reset", "unknown")

    if response.status_code == 403:
        print()
        print(f"Rate limit hit for query: {query}")
        print(f"Remaining: {remaining}")
        print(f"Reset timestamp: {reset_time}")
        print("Stopping safely. Already collected rows will remain saved.")
        return None

    if response.status_code != 200:
        print()
        print(f"GitHub API error for query '{query}': {response.status_code}")
        print(response.text[:300])
        print("Stopping safely so this query is not incorrectly marked complete.")
        return None

    data = response.json()
    items = data.get("items", [])

    rows = []

    for repo in items:
        rows.append({
            "title": repo.get("full_name", ""),
            "content": build_repo_content(repo, query),
            "category": category,
            "source_type": "github_repository",
            "url": repo.get("html_url", ""),
            "tags": build_tags(repo, query),
            "difficulty": infer_difficulty(repo),
            "target_roles": infer_target_roles(category),
            "skills": infer_skills(category, repo),
            "project_type": "implementation_reference",
            "freshness": "live_github",
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "language": repo.get("language", ""),
            "updated_at": repo.get("updated_at", "")
        })

    print(f"Collected {len(rows)} repos | remaining API calls: {remaining}")
    return rows


def build_repo_content(repo: Dict, query: str) -> str:
    name = repo.get("full_name", "")
    description = repo.get("description") or ""
    language = repo.get("language") or "Unknown"
    stars = repo.get("stargazers_count", 0)
    forks = repo.get("forks_count", 0)
    updated_at = repo.get("updated_at", "")

    return (
        f"GitHub repository {name}. Description: {description}. "
        f"Matched search topic: {query}. Primary language: {language}. "
        f"Stars: {stars}. Forks: {forks}. Last updated: {updated_at}. "
        f"This repository provides implementation signals, architecture inspiration, "
        f"technology choices, and realistic project-building patterns."
    )


def build_tags(repo: Dict, query: str) -> str:
    topics = repo.get("topics", []) or []
    language = repo.get("language") or ""

    tags = list(topics)
    tags.append(query)

    if language:
        tags.append(language)

    return ",".join(
        str(tag).lower().replace(" ", "-")
        for tag in tags
        if tag
    )


def infer_difficulty(repo: Dict) -> str:
    stars = repo.get("stargazers_count", 0)

    if stars >= 5000:
        return "high"

    if stars >= 500:
        return "medium"

    return "medium"


def infer_target_roles(category: str) -> str:
    role_map = {
        "frontend": "Frontend Engineer, Full-Stack Engineer, UI Engineer",
        "backend": "Backend Engineer, Platform Engineer, Software Engineer",
        "rag_llm": "AI Engineer, LLM Application Engineer, NLP Engineer",
        "mlops": "MLOps Engineer, ML Engineer, Platform Engineer",
        "data_engineering": "Data Engineer, Analytics Engineer, Data Platform Engineer",
        "cybersecurity": "Security Engineer, Cybersecurity Analyst, DevSecOps Engineer",
        "cloud": "Cloud Engineer, DevOps Engineer, Platform Engineer",
        "devops": "DevOps Engineer, Platform Engineer, SRE",
        "computer_vision": "Computer Vision Engineer, ML Engineer, AI Engineer",
        "fintech": "FinTech Engineer, ML Engineer, Data Scientist",
        "developer_tools": "Developer Tools Engineer, Software Engineer, Platform Engineer",
        "healthcare_ai": "Healthcare AI Engineer, ML Engineer, Data Scientist"
    }

    return role_map.get(category, "Software Engineer, Full-Stack Engineer")


def infer_skills(category: str, repo: Dict) -> str:
    language = repo.get("language") or ""

    skill_map = {
        "frontend": ["React", "TypeScript", "UI Architecture", "Frontend Engineering"],
        "backend": ["API Design", "Backend Engineering", "Databases", "System Design"],
        "rag_llm": ["RAG", "Semantic Search", "LLM Evaluation", "Embeddings"],
        "mlops": ["MLOps", "Model Monitoring", "Experiment Tracking", "Model Deployment"],
        "data_engineering": ["ETL", "Data Quality", "SQL", "Pipeline Monitoring"],
        "cybersecurity": ["Security Analytics", "Risk Scoring", "Threat Detection"],
        "cloud": ["Cloud Architecture", "Cost Optimization", "Monitoring"],
        "devops": ["CI/CD", "Automation", "Observability", "Reliability"],
        "computer_vision": ["Computer Vision", "OCR", "Object Detection"],
        "fintech": ["Fraud Detection", "Risk Scoring", "Financial Analytics"],
        "developer_tools": ["Code Analysis", "GitHub APIs", "Developer Productivity"],
        "healthcare_ai": ["Healthcare Analytics", "NLP", "Clinical Data"]
    }

    skills = list(skill_map.get(category, ["Software Engineering"]))

    if language:
        skills.append(language)

    return ", ".join(skills)


def build_github_project_corpus() -> None:
    existing_rows = load_existing_rows()
    all_rows = list(existing_rows)

    seen_urls = {
        row.get("url", "")
        for row in all_rows
        if row.get("url", "")
    }

    state = load_ingestion_state(len(all_rows))
    completed_queries = set(state.get("completed_queries", []))

    print(f"Existing rows loaded: {len(all_rows)}")
    print("GitHub token active:", bool(os.getenv("GITHUB_TOKEN")))
    print(f"Completed searches remembered: {len(completed_queries)}")
    print()

    try:
        for category, queries in SEARCH_TOPICS.items():
            for query in queries:
                query_key = make_query_key(category, query)

                if query_key in completed_queries:
                    print(f"Skipping completed search: {category} | {query}")
                    continue

                print(f"Searching GitHub: {category} | {query}")

                rows = search_github_repositories(
                    query=query,
                    category=category
                )

                # None means rate-limited or another API error.
                # Stop safely and keep all saved data.
                if rows is None:
                    save_rows(all_rows)
                    save_ingestion_state(
                        {"completed_queries": sorted(completed_queries)}
                    )
                    print("Stopped safely because GitHub rejected further requests.")
                    return

                # An empty list means the search succeeded but found no matches.
                # That is normal; mark this query complete and continue.
                if not rows:
                    print("No repositories matched this query. Skipping and continuing.")
                    completed_queries.add(query_key)
                    save_ingestion_state(
                        {"completed_queries": sorted(completed_queries)}
                    )
                    time.sleep(SLEEP_SECONDS)
                    continue

                new_count = 0

                for row in rows:
                    url = row.get("url", "")

                    if url and url not in seen_urls:
                        all_rows.append(row)
                        seen_urls.add(url)
                        new_count += 1

                completed_queries.add(query_key)

                print(f"New unique repos added: {new_count}")
                save_rows(all_rows)
                save_ingestion_state(
                    {"completed_queries": sorted(completed_queries)}
                )

                time.sleep(SLEEP_SECONDS)

    except KeyboardInterrupt:
        print()
        print("Interrupted by user. Saving collected rows before exit...")
        save_rows(all_rows)
        save_ingestion_state(
            {"completed_queries": sorted(completed_queries)}
        )
        return

    save_rows(all_rows)
    save_ingestion_state(
        {"completed_queries": sorted(completed_queries)}
    )

    print()
    print(f"GitHub corpus collection finished.")
    print(f"Total rows: {len(all_rows)}")

    if all_rows:
        df = pd.DataFrame(all_rows)
        print()
        print("Category counts:")
        print(df["category"].value_counts())


if __name__ == "__main__":
    build_github_project_corpus()
