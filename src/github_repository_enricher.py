import base64
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd
import requests


TRUSTED_REPOSITORIES_PATH = "data/trusted_github_repositories.csv"
OUTPUT_PATH = "data/github_repository_details.csv"

GITHUB_API_BASE = "https://api.github.com"
README_MAX_CHARACTERS = 5000
SLEEP_SECONDS = 0.5


ARCHITECTURE_SIGNALS = {
    "document_ingestion": [
        "ingestion",
        "document loader",
        "document parsing",
        "data ingestion",
        "file upload",
    ],
    "retrieval_and_search": [
        "retrieval",
        "semantic search",
        "vector search",
        "embedding",
        "reranking",
    ],
    "vector_database": [
        "vector database",
        "vector store",
        "faiss",
        "chroma",
        "qdrant",
        "weaviate",
        "milvus",
        "pgvector",
    ],
    "knowledge_graph": [
        "knowledge graph",
        "graph database",
        "graph rag",
        "neo4j",
    ],
    "api_service_layer": [
        "fastapi",
        "flask",
        "rest api",
        "graphql",
        "api server",
    ],
    "web_dashboard": [
        "streamlit",
        "react",
        "dashboard",
        "web ui",
        "frontend",
    ],
    "evaluation_and_monitoring": [
        "evaluation",
        "monitoring",
        "observability",
        "metrics",
        "drift",
        "benchmark",
    ],
    "experiment_tracking": [
        "experiment tracking",
        "model registry",
        "model versioning",
        "run tracking",
    ],
    "deployment_and_containers": [
        "docker",
        "kubernetes",
        "deployment",
        "container",
        "helm",
    ],
    "cloud_and_serverless": [
        "aws",
        "azure",
        "gcp",
        "serverless",
        "lambda",
        "cloud",
    ],
    "fraud_and_risk_modeling": [
        "fraud",
        "risk scoring",
        "anomaly detection",
        "transaction",
    ],
    "clinical_nlp": [
        "clinical",
        "healthcare",
        "medical",
        "ehr",
        "patient",
    ],
    "computer_vision": [
        "object detection",
        "image processing",
        "opencv",
        "yolo",
        "computer vision",
    ],
}


TECHNOLOGY_SIGNALS = {
    "Python": ["python"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Streamlit": ["streamlit"],
    "React": ["react"],
    "TypeScript": ["typescript"],
    "JavaScript": ["javascript"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Redis": ["redis"],
    "FAISS": ["faiss"],
    "Chroma": ["chroma"],
    "Qdrant": ["qdrant"],
    "Neo4j": ["neo4j"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "keras"],
    "Pandas": ["pandas"],
    "OpenCV": ["opencv"],
    "AWS": ["aws", "amazon web services"],
    "GitHub Actions": ["github actions"],
}


def get_headers() -> Dict[str, str]:
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Export your token in this terminal first."
        )

    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def load_existing_details() -> pd.DataFrame:
    if not os.path.exists(OUTPUT_PATH):
        return pd.DataFrame()

    try:
        return pd.read_csv(OUTPUT_PATH).fillna("")
    except Exception:
        return pd.DataFrame()


def save_details(df: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(df)} enriched repositories to {OUTPUT_PATH}")


def fetch_readme(repository_name: str) -> Dict[str, str]:
    url = f"{GITHUB_API_BASE}/repos/{repository_name}/readme"

    response = requests.get(
        url,
        headers=get_headers(),
        timeout=30,
    )

    remaining = response.headers.get("X-RateLimit-Remaining", "unknown")

    if response.status_code == 404:
        return {
            "status": "no_readme",
            "readme_text": "",
            "remaining": remaining,
        }

    if response.status_code != 200:
        return {
            "status": f"api_error_{response.status_code}",
            "readme_text": "",
            "remaining": remaining,
        }

    payload = response.json()
    encoded_content = payload.get("content", "")

    try:
        readme_text = base64.b64decode(
            encoded_content
        ).decode("utf-8", errors="ignore")
    except Exception:
        readme_text = ""

    return {
        "status": "success",
        "readme_text": readme_text,
        "remaining": remaining,
    }


def clean_readme_text(readme_text: str) -> str:
    text = str(readme_text)

    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    text = re.sub(r"[#>*_`~]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text[:README_MAX_CHARACTERS]


def extract_signals(text: str, signal_map: Dict[str, List[str]]) -> List[str]:
    lowered_text = text.lower()
    matches = []

    for signal, keywords in signal_map.items():
        if any(keyword in lowered_text for keyword in keywords):
            matches.append(signal)

    return matches


def enrich_repositories() -> None:
    if not os.path.exists(TRUSTED_REPOSITORIES_PATH):
        raise FileNotFoundError(
            f"Trusted repository file not found: {TRUSTED_REPOSITORIES_PATH}"
        )

    trusted_df = pd.read_csv(TRUSTED_REPOSITORIES_PATH).fillna("")
    existing_df = load_existing_details()

    existing_titles = set()

    if not existing_df.empty and "title" in existing_df.columns:
        existing_titles = set(existing_df["title"].astype(str))

    rows = []

    if not existing_df.empty:
        rows.extend(existing_df.to_dict("records"))

    print(f"Trusted repositories: {len(trusted_df)}")
    print(f"Already enriched: {len(existing_titles)}")
    print()

    for _, repository in trusted_df.iterrows():
        title = str(repository["title"])

        if title in existing_titles:
            print(f"Skipping already enriched: {title}")
            continue

        print(f"Fetching README: {title}")

        result = fetch_readme(title)
        cleaned_readme = clean_readme_text(result["readme_text"])

        architecture_signals = extract_signals(
            cleaned_readme,
            ARCHITECTURE_SIGNALS,
        )

        technology_signals = extract_signals(
            cleaned_readme,
            TECHNOLOGY_SIGNALS,
        )

        row = repository.to_dict()
        row["readme_status"] = result["status"]
        row["readme_excerpt"] = cleaned_readme
        row["architecture_signals"] = ", ".join(architecture_signals)
        row["technology_signals"] = ", ".join(technology_signals)
        row["enriched_at_utc"] = datetime.now(
            timezone.utc
        ).isoformat()

        rows.append(row)

        enriched_df = pd.DataFrame(rows)
        save_details(enriched_df)

        print(
            f"README status: {result['status']} | "
            f"Core requests remaining: {result['remaining']}"
        )

        time.sleep(SLEEP_SECONDS)

    final_df = pd.DataFrame(rows)
    save_details(final_df)

    print()
    print("README enrichment completed.")
    print(f"Total enriched repositories: {len(final_df)}")


if __name__ == "__main__":
    enrich_repositories()
