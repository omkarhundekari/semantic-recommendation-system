from typing import Dict, List

from embedding_search import search_papers
from github_corpus_search import search_github_project_corpus
from project_corpus_search import search_project_corpus
from query_expander import get_query_metadata


def retrieve_evidence(user_query: str, top_k: int = 3) -> Dict:
    query_metadata = get_query_metadata(user_query)

    expanded_query = query_metadata["expanded_query"]
    detected_domain = query_metadata["detected_domain"]
    detected_intent = query_metadata["detected_intent"]

    route = choose_source_route(
        detected_domain=detected_domain,
        detected_intent=detected_intent,
        user_query=user_query
    )

    research_results = []
    project_results = []
    github_results = []

    if route in ["research", "both"]:
        research_results = search_papers(
            expanded_query,
            top_k=max(top_k, 3)
        )

        for item in research_results:
            item["source_type"] = "research_paper"

    if route in ["project", "both"]:
        project_results = search_project_corpus(
            expanded_query,
            top_k=max(top_k, 3),
            domain_filter=detected_domain
        )

        for item in project_results:
            item["source_type"] = item.get(
                "source_type",
                "project_pattern"
            )

        github_results = search_github_project_corpus(
            expanded_query,
            top_k=max(top_k, 3),
            domain_filter=detected_domain
        )

        for item in github_results:
            item["source_type"] = "github_repository"

    merged_results = merge_evidence(
        research_results=research_results,
        project_results=project_results,
        github_results=github_results,
        route=route,
        top_k=top_k
    )

    return {
        "query": user_query,
        "expanded_query": expanded_query,
        "detected_domain": detected_domain,
        "detected_intent": detected_intent,
        "selected_route": route,
        "research_results": research_results,
        "project_results": project_results,
        "github_results": github_results,
        "merged_results": merged_results
    }


def choose_source_route(
    detected_domain: str,
    detected_intent: str,
    user_query: str
) -> str:
    query = user_query.lower()

    explicit_project_keywords = [
        "project",
        "projects",
        "app",
        "tool",
        "dashboard",
        "platform",
        "portfolio",
        "build",
        "make",
        "create",
        "prototype",
        "mvp"
    ]

    explicit_research_keywords = [
        "research",
        "paper",
        "papers",
        "survey",
        "literature",
        "method",
        "methods",
        "model",
        "models",
        "architecture",
        "algorithm",
        "benchmark",
        "evaluation"
    ]

    research_first_topics = [
        "rag",
        "retrieval augmented generation",
        "retrieval-augmented generation",
        "retrieval",
        "question answering",
        "recommendation",
        "recommender",
        "graph neural network",
        "gnn",
        "knowledge graph",
        "nlp",
        "transformer",
        "large language model",
        "llm",
        "semantic search",
        "machine learning",
        "deep learning"
    ]

    project_first_domains = [
        "frontend",
        "backend",
        "full_stack",
        "devops",
        "cloud",
        "mobile",
        "developer_tools",
        "education_tech",
        "blockchain",
        "databases"
    ]

    mixed_domains = [
        "ai_ml",
        "rag_llm",
        "mlops",
        "data_engineering",
        "cybersecurity",
        "healthcare_ai",
        "computer_vision",
        "fintech",
        "nlp",
        "recommendation_systems"
    ]

    has_project_intent = (
        detected_intent == "project_building"
        or any(keyword in query for keyword in explicit_project_keywords)
    )

    has_research_intent = any(
        keyword in query
        for keyword in explicit_research_keywords
    )

    has_research_topic = any(
        topic in query
        for topic in research_first_topics
    )

    research_supported_project_domains = [
        "rag_llm",
        "ai_ml",
        "healthcare_ai",
        "computer_vision",
        "nlp",
        "recommendation_systems"
    ]

    implementation_first_project_domains = [
        "frontend",
        "backend",
        "full_stack",
        "cloud",
        "devops",
        "mlops",
        "data_engineering",
        "databases",
        "cybersecurity",
        "fintech",
        "developer_tools",
        "mobile",
        "blockchain",
        "education_tech"
    ]

    if has_research_intent and not has_project_intent:
        return "research"

    if has_project_intent:
        if detected_domain in research_supported_project_domains:
            return "both"

        if detected_domain in implementation_first_project_domains:
            return "project"

    if has_research_topic and has_project_intent:
        return "both"

    if detected_domain in project_first_domains:
        return "project"

    if detected_domain in mixed_domains:
        return "research"

    if has_project_intent:
        return "project"

    return "both"


def merge_evidence(
    research_results: List[Dict],
    project_results: List[Dict],
    github_results: List[Dict],
    route: str,
    top_k: int
) -> List[Dict]:
    """
    Keeps the three evidence types balanced.

    Project queries:
    curated project pattern → GitHub implementation reference → repeat

    Mixed queries:
    curated project pattern → research paper → GitHub reference → repeat

    Pure research queries:
    research papers only
    """
    if route == "research":
        return research_results[:top_k]

    merged = []

    if route == "project":
        max_len = max(
            len(project_results),
            len(github_results)
        )

        for index in range(max_len):
            if index < len(project_results):
                merged.append(project_results[index])

            if index < len(github_results):
                merged.append(github_results[index])

        return merged[:top_k]

    max_len = max(
        len(project_results),
        len(research_results),
        len(github_results)
    )

    for index in range(max_len):
        if index < len(project_results):
            merged.append(project_results[index])

        if index < len(research_results):
            merged.append(research_results[index])

        if index < len(github_results):
            merged.append(github_results[index])

    return merged[:top_k]
