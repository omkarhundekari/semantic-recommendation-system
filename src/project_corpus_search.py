import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from semantic_engine import SemanticEngine


PROJECT_CORPUS_PATH = "data/project_corpus.csv"

project_df = None
project_documents = []
project_engine = None
project_embeddings = None


DOMAIN_CATEGORY_MAP = {
    "frontend": ["frontend"],
    "backend": ["backend", "databases", "full_stack"],
    "full_stack": ["full_stack", "frontend", "backend", "rag_llm"],
    "rag_llm": ["rag_llm", "ai_ml", "full_stack", "developer_tools"],
    "ai_ml": ["ai_ml", "rag_llm", "mlops", "computer_vision", "nlp", "recommendation_systems"],
    "mlops": ["mlops", "ai_ml", "devops", "cloud"],
    "data_engineering": ["data_engineering", "databases", "cloud", "mlops"],
    "databases": ["databases", "backend", "data_engineering"],
    "cloud": ["cloud", "devops"],
    "devops": ["devops", "cloud", "developer_tools"],
    "cybersecurity": ["cybersecurity", "developer_tools", "blockchain"],
    "security": ["cybersecurity", "developer_tools", "blockchain"],
    "healthcare_ai": ["healthcare_ai", "ai_ml", "data_engineering"],
    "blockchain": ["blockchain", "cybersecurity"],
    "mobile": ["mobile", "frontend", "full_stack"],
    "computer_vision": ["computer_vision", "ai_ml"],
    "nlp": ["nlp", "rag_llm", "ai_ml"],
    "recommendation_systems": ["recommendation_systems", "ai_ml", "data_engineering"],
    "education_tech": ["education_tech", "ai_ml", "full_stack"],
    "fintech": ["fintech", "cybersecurity", "data_engineering"],
    "developer_tools": ["developer_tools", "frontend", "backend", "devops", "rag_llm"],
    "general": []
}


MIN_SIMILARITY_SCORE = 0.15


def load_project_corpus():
    global project_df, project_documents, project_engine, project_embeddings

    if project_df is not None:
        return

    if not os.path.exists(PROJECT_CORPUS_PATH):
        raise FileNotFoundError(f"Project corpus not found at {PROJECT_CORPUS_PATH}")

    project_df = pd.read_csv(PROJECT_CORPUS_PATH)
    project_df.columns = project_df.columns.str.strip()
    project_df = project_df.fillna("")

    required_columns = [
        "title",
        "content",
        "category",
        "source_type",
        "url",
        "tags",
        "difficulty",
        "target_roles"
    ]

    missing_columns = [
        column for column in required_columns
        if column not in project_df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in project corpus: {missing_columns}"
        )

    project_documents = (
        project_df["title"].astype(str)
        + " "
        + project_df["content"].astype(str)
        + " "
        + project_df["category"].astype(str)
        + " "
        + project_df["tags"].astype(str)
        + " "
        + project_df["target_roles"].astype(str)
    ).tolist()

    project_engine = SemanticEngine()
    project_embeddings = normalize_embeddings(
        project_engine.create_embeddings(project_documents)
    )


def search_project_corpus(
    query: str,
    top_k: int = 5,
    domain_filter: Optional[str] = None
) -> List[Dict]:
    load_project_corpus()

    if not project_documents:
        return []

    query_embedding = normalize_embeddings(
        project_engine.create_embeddings([query])
    )

    similarity_scores = safe_cosine_similarity(
        query_embedding,
        project_embeddings
    )

    ranked_indices = np.argsort(similarity_scores)[::-1]

    filtered_indices = apply_domain_filter(
        ranked_indices=ranked_indices,
        domain_filter=domain_filter
    )

    selected_indices = []

    for index in filtered_indices:
        score = float(similarity_scores[int(index)])

        if score >= MIN_SIMILARITY_SCORE:
            selected_indices.append(int(index))

        if len(selected_indices) >= top_k:
            break

    results = []

    for index in selected_indices:
        row = project_df.iloc[int(index)]

        results.append({
            "title": row.get("title", "Untitled Project Pattern"),
            "abstract": row.get("content", ""),
            "content": row.get("content", ""),
            "category": row.get("category", "general"),
            "source_type": row.get("source_type", "project_pattern"),
            "url": row.get("url", ""),
            "tags": row.get("tags", ""),
            "difficulty": row.get("difficulty", ""),
            "target_roles": row.get("target_roles", ""),
            "score": float(similarity_scores[int(index)])
        })

    return results


def apply_domain_filter(
    ranked_indices,
    domain_filter: Optional[str]
) -> List[int]:
    normalized_domain = normalize_domain(domain_filter)

    allowed_categories = DOMAIN_CATEGORY_MAP.get(normalized_domain, [])

    if normalized_domain == "general" or not allowed_categories:
        return [int(index) for index in ranked_indices]

    filtered_indices = []

    for index in ranked_indices:
        row = project_df.iloc[int(index)]
        category = str(row.get("category", "")).strip().lower()

        if category in allowed_categories:
            filtered_indices.append(int(index))

    return filtered_indices


def normalize_domain(domain: Optional[str]) -> str:
    if not domain:
        return "general"

    domain = str(domain).lower().strip()

    aliases = {
        "front_end": "frontend",
        "front-end": "frontend",
        "ai": "ai_ml",
        "ml": "ai_ml",
        "machine_learning": "ai_ml",
        "security": "cybersecurity",
        "cyber_security": "cybersecurity",
        "cyber-security": "cybersecurity",
        "data": "data_engineering",
        "healthcare": "healthcare_ai",
        "healthcare ai": "healthcare_ai",
        "education": "education_tech",
        "edtech": "education_tech",
        "developer tools": "developer_tools",
        "fullstack": "full_stack",
        "full-stack": "full_stack"
    }

    return aliases.get(domain, domain)


def normalize_embeddings(embeddings):
    if hasattr(embeddings, "detach"):
        embeddings = embeddings.detach().cpu().numpy()

    embeddings = np.asarray(embeddings, dtype=np.float64)

    embeddings = np.nan_to_num(
        embeddings,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    embeddings = np.clip(embeddings, -1.0e6, 1.0e6)

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.nan_to_num(
        norms,
        nan=1.0,
        posinf=1.0,
        neginf=1.0
    )
    norms = np.where(norms == 0.0, 1.0, norms)

    normalized = embeddings / norms

    normalized = np.nan_to_num(
        normalized,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    return normalized.astype(np.float32)


def safe_cosine_similarity(query_embedding, document_embeddings):
    query_embedding = np.nan_to_num(
        np.asarray(query_embedding, dtype=np.float32),
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    document_embeddings = np.nan_to_num(
        np.asarray(document_embeddings, dtype=np.float32),
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        scores = np.dot(query_embedding, document_embeddings.T)[0]

    scores = np.nan_to_num(
        scores,
        nan=0.0,
        posinf=0.0,
        neginf=0.0
    )

    return scores
