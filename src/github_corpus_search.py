import os
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from semantic_engine import SemanticEngine


GITHUB_CORPUS_PATH = "data/github_project_corpus.csv"
MIN_SIMILARITY_SCORE = 0.12

NON_IMPLEMENTATION_TERMS = [
    "awesome list",
    "curated list",
    "tutorial",
    "tutorials",
    "workshop",
    "course material",
    "course materials",
    "summer school",
    "learning resource",
    "learning resources",
    "comprehensive list",
    "conference materials",
]

IMPLEMENTATION_SIGNAL_TERMS = [
    "platform",
    "dashboard",
    "server",
    "assistant",
    "monitoring",
    "detection",
    "tracking",
    "engine",
    "pipeline",
    "system",
    "tool",
    "framework",
    "library",
    "api",
]


github_df = None
github_documents = None
github_engine = None
github_embeddings = None


DOMAIN_CATEGORY_MAP = {
    "frontend": ["frontend"],
    "backend": ["backend"],
    "full_stack": ["frontend", "backend", "developer_tools"],
    "rag_llm": ["rag_llm"],
    "ai_ml": ["rag_llm", "mlops", "computer_vision", "healthcare_ai"],
    "mlops": ["mlops", "devops", "cloud"],
    "data_engineering": ["data_engineering", "cloud", "devops"],
    "databases": ["backend", "data_engineering"],
    "cloud": ["cloud", "devops", "mlops"],
    "devops": ["devops", "cloud", "mlops"],
    "cybersecurity": ["cybersecurity"],
    "security": ["cybersecurity"],
    "healthcare_ai": ["healthcare_ai"],
    "computer_vision": ["computer_vision"],
    "nlp": ["rag_llm", "healthcare_ai"],
    "recommendation_systems": ["rag_llm", "data_engineering"],
    "fintech": ["fintech", "cybersecurity"],
    "developer_tools": ["developer_tools", "devops", "backend"],
    "general": []
}


def load_github_corpus() -> None:
    """
    Loads the saved GitHub repository corpus once and creates embeddings
    that can be reused for every later query.
    """
    global github_df
    global github_documents
    global github_engine
    global github_embeddings

    if github_df is not None:
        return

    if not os.path.exists(GITHUB_CORPUS_PATH):
        raise FileNotFoundError(
            f"GitHub corpus not found: {GITHUB_CORPUS_PATH}. "
            "Run github_project_ingestor.py first."
        )

    github_df = pd.read_csv(GITHUB_CORPUS_PATH).fillna("")

    required_columns = {
        "title",
        "content",
        "category",
        "source_type",
        "url",
        "stars",
        "language",
        "updated_at"
    }

    missing = required_columns - set(github_df.columns)

    if missing:
        raise ValueError(
            f"GitHub corpus is missing required columns: {sorted(missing)}"
        )

    github_documents = []

    for _, row in github_df.iterrows():
        document = (
            f"Repository: {row['title']}. "
            f"Description: {row['content']}. "
            f"Category: {row['category']}. "
            f"Tags: {row.get('tags', '')}. "
            f"Skills: {row.get('skills', '')}. "
            f"Primary language: {row.get('language', '')}. "
            f"GitHub stars: {row.get('stars', 0)}."
        )

        github_documents.append(document)

    github_engine = SemanticEngine()

    raw_embeddings = github_engine.create_embeddings(github_documents)
    github_embeddings = normalize_embeddings(raw_embeddings)

    print(f"Loaded GitHub implementation corpus: {len(github_df)} repositories")



def is_non_implementation_reference(item: Dict) -> bool:
    title = str(item.get("title", "")).lower()
    content = str(item.get("content", "")).lower()
    combined_text = f"{title} {content}"

    return any(
        term in combined_text
        for term in NON_IMPLEMENTATION_TERMS
    )


def calculate_quality_score(item: Dict) -> float:
    semantic_score = float(item.get("score", 0.0))
    stars = int(item.get("stars", 0) or 0)
    language = str(item.get("language", "")).strip().lower()
    title = str(item.get("title", "")).lower()
    content = str(item.get("content", "")).lower()
    combined_text = f"{title} {content}"

    quality_score = semantic_score

    # Popularity is a small supporting signal, not the main ranking factor.
    quality_score += min(np.log10(max(stars, 1)) * 0.02, 0.08)

    if any(term in combined_text for term in IMPLEMENTATION_SIGNAL_TERMS):
        quality_score += 0.04

    # Missing language metadata is a mild warning, not a rejection.
    if language in {"", "nan", "unknown"}:
        quality_score -= 0.03

    return round(quality_score, 4)


def apply_quality_filter(candidates: List[Dict]) -> List[Dict]:
    filtered = []

    for item in candidates:
        if is_non_implementation_reference(item):
            continue

        item["quality_score"] = calculate_quality_score(item)
        filtered.append(item)

    return filtered


def deduplicate_repository_names(candidates: List[Dict]) -> List[Dict]:
    unique_candidates = []
    seen_names = set()

    for item in candidates:
        title = str(item.get("title", ""))
        repository_name = title.split("/", 1)[-1]
        normalized_name = (
            repository_name.lower()
            .replace("-", " ")
            .replace("_", " ")
            .strip()
        )

        if normalized_name in seen_names:
            continue

        seen_names.add(normalized_name)
        unique_candidates.append(item)

    return unique_candidates


def search_github_project_corpus(
    query: str,
    top_k: int = 5,
    domain_filter: Optional[str] = None
) -> List[Dict]:
    """
    Searches live GitHub implementation references stored locally.
    """
    load_github_corpus()

    raw_query_embedding = github_engine.create_query_embedding(query)
    query_embedding = normalize_embeddings(raw_query_embedding)[0]

    scores = np.dot(github_embeddings, query_embedding)
    scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

    candidates = []

    for index, score in enumerate(scores):
        row = github_df.iloc[index]

        stars_value = row.get("stars", 0)

        try:
            stars = int(float(stars_value))
        except (TypeError, ValueError):
            stars = 0

        candidates.append({
            "title": row["title"],
            "abstract": row["content"],
            "content": row["content"],
            "category": row["category"],
            "source_type": "github_repository",
            "url": row["url"],
            "tags": row.get("tags", ""),
            "difficulty": row.get("difficulty", ""),
            "target_roles": row.get("target_roles", ""),
            "skills": row.get("skills", ""),
            "project_type": row.get("project_type", ""),
            "freshness": row.get("freshness", ""),
            "stars": stars,
            "language": row.get("language", ""),
            "updated_at": row.get("updated_at", ""),
            "score": float(score)
        })

    filtered = apply_domain_filter(candidates, domain_filter)

    filtered = [
        item
        for item in filtered
        if item["score"] >= MIN_SIMILARITY_SCORE
    ]

    filtered = apply_quality_filter(filtered)
    filtered = deduplicate_repository_names(filtered)

    filtered.sort(
        key=lambda item: (
            item.get("quality_score", 0.0),
            item["score"],
            item["stars"]
        ),
        reverse=True
    )

    return filtered[:top_k]


def apply_domain_filter(
    candidates: List[Dict],
    domain_filter: Optional[str]
) -> List[Dict]:
    normalized_domain = normalize_domain(domain_filter)

    if normalized_domain == "general":
        return candidates

    allowed_categories = DOMAIN_CATEGORY_MAP.get(normalized_domain, [])

    if not allowed_categories:
        return []

    return [
        item
        for item in candidates
        if item.get("category") in allowed_categories
    ]


def normalize_domain(domain: Optional[str]) -> str:
    if not domain:
        return "general"

    aliases = {
        "data": "data_engineering",
        "data engineer": "data_engineering",
        "healthcare": "healthcare_ai",
        "health": "healthcare_ai",
        "security": "cybersecurity",
        "developer tools": "developer_tools",
        "computer vision": "computer_vision",
        "full stack": "full_stack",
        "fullstack": "full_stack",
        "rag": "rag_llm",
        "llm": "rag_llm",
        "machine learning": "ai_ml",
        "machine_learning": "ai_ml"
    }

    normalized = str(domain).strip().lower()

    return aliases.get(normalized, normalized)


def normalize_embeddings(embeddings) -> np.ndarray:
    """
    Converts embeddings safely into normalized NumPy vectors.
    This prevents the earlier MPS/NumPy conversion issue.
    """
    if hasattr(embeddings, "detach"):
        embeddings = embeddings.detach()

    if hasattr(embeddings, "cpu"):
        embeddings = embeddings.cpu()

    if hasattr(embeddings, "numpy"):
        embeddings = embeddings.numpy()

    array = np.asarray(embeddings, dtype=np.float32)

    if array.ndim == 1:
        array = array.reshape(1, -1)

    norms = np.linalg.norm(array, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-12, None)

    return array / norms
