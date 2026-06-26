import re
from typing import Any, Dict, List, Mapping, Tuple


SIGNAL_GROUPS = {
    "methods": {
        "retrieval": ["retrieval", "retrieve", "retriever"],
        "reranking": ["reranking", "rerank"],
        "embeddings": ["embedding", "embeddings"],
        "knowledge_graphs": [
            "knowledge graph",
            "knowledge graphs",
            "graph rag",
            "graph-based",
        ],
        "classification": ["classification", "classifier"],
        "anomaly_detection": ["anomaly detection", "outlier detection"],
        "deep_learning": [
            "deep learning",
            "neural network",
            "transformer",
        ],
        "explainability": [
            "explainability",
            "interpretable",
            "interpretability",
        ],
    },
    "datasets": {
        "dataset_mentions": ["dataset", "datasets", "corpus", "corpora"],
        "natural_questions": ["natural questions"],
        "triviaqa": ["triviaqa", "trivia qa"],
    },
    "benchmarks": {
        "benchmarks": ["benchmark", "benchmarks", "benchmarking"],
    },
    "limitations": {
        "hallucination_risk": ["hallucination", "ungrounded"],
        "retrieval_quality": [
            "retrieval quality",
            "irrelevant context",
            "poor retrieval",
        ],
        "data_quality": ["data quality", "missing data", "noisy data"],
        "latency_and_cost": [
            "latency",
            "resource intensive",
            "computational cost",
        ],
        "fairness_and_bias": ["fairness", "bias", "biased"],
        "deployment_reliability": [
            "deployment",
            "reliability",
            "production",
        ],
    },
    "applications": {
        "question_answering": [
            "question answering",
            "question-answering",
            "qa system",
            "open-domain question answering",
        ],
        "search_and_discovery": [
            "search",
            "discovery",
            "information retrieval",
        ],
        "monitoring": ["monitoring", "observability", "drift"],
        "fraud_and_risk": ["fraud", "risk scoring", "transaction"],
        "cloud_optimization": [
            "cloud",
            "cost optimization",
            "resource optimization",
        ],
        "developer_productivity": [
            "developer",
            "code review",
            "repository",
        ],
    },
    "implementation": {
        "api_service": ["api", "rest", "fastapi", "service"],
        "dashboard": ["dashboard", "visualization", "visualise"],
        "database": [
            "database",
            "postgresql",
            "sql",
            "vector database",
        ],
        "deployment": [
            "docker",
            "kubernetes",
            "deployment",
            "production",
        ],
    },
    "risks": {
        "security": ["security", "attack", "vulnerability", "zero trust"],
        "privacy": ["privacy", "private data", "sensitive data"],
        "bias": ["bias", "fairness", "biased"],
        "reliability": ["reliability", "failure", "fault", "robustness"],
    },
    "trends": {
        "rag": [
            "retrieval-augmented generation",
            "retrieval augmented generation",
            "rag",
        ],
        "llm": [
            "large language model",
            "large language models",
            "llm",
            "llms",
        ],
        "agents": ["agent", "agents", "agentic"],
        "multimodal": ["multimodal", "multi-modal"],
    },
    "evaluation": {
        "benchmarks": ["benchmark", "benchmarks", "benchmarking"],
        "metrics": ["metric", "metrics", "precision", "recall", "f1"],
        "experiments": ["experiment", "experiments", "experimental"],
        "comparisons": [
            "comparison",
            "comparisons",
            "compared with",
            "baseline",
            "ablation",
            "outperforms",
            "state-of-the-art",
        ],
    },
}

SIGNAL_ORDER = [
    "methods",
    "datasets",
    "benchmarks",
    "limitations",
    "applications",
    "implementation",
    "risks",
    "trends",
    "evaluation",
]

TAG_BY_SIGNAL_GROUP = {
    "methods": "method",
    "datasets": "dataset",
    "benchmarks": "benchmark",
    "limitations": "limitation",
    "applications": "application",
    "implementation": "implementation",
    "risks": "risk",
    "trends": "trend",
}


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def split_sentences(text: str) -> List[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def find_matching_phrases(
    text: str,
    phrases: List[str],
) -> List[str]:
    matches = []

    for phrase in phrases:
        normalized_phrase = normalize_text(phrase)

        if normalized_phrase and normalized_phrase in text:
            matches.append(normalized_phrase)

    return matches


def build_evidence_snippets(
    text: str,
    matched_phrases: Dict[str, List[str]],
    limit: int = 4,
) -> List[str]:
    phrases = {
        phrase
        for phrase_list in matched_phrases.values()
        for phrase in phrase_list
    }

    snippets = []

    for sentence in split_sentences(text):
        normalized_sentence = normalize_text(sentence)

        if any(phrase in normalized_sentence for phrase in phrases):
            snippets.append(sentence)

        if len(snippets) >= limit:
            break

    return snippets


def build_signal_snippets(
    text: str,
    matched_phrases: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    signal_snippets = {}

    for signal, phrases in matched_phrases.items():
        snippets = []

        for sentence in split_sentences(text):
            normalized_sentence = normalize_text(sentence)

            if any(phrase in normalized_sentence for phrase in phrases):
                snippets.append(sentence)

        if snippets:
            signal_snippets[signal] = snippets

    return signal_snippets


def extract_research_evidence(
    paper: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Extract deterministic, paper-level evidence from title and abstract text.

    This function does not make feasibility or recommendation decisions.
    It only returns traceable signals that later policy layers can aggregate.
    """
    title = str(paper.get("title", "") or "").strip()
    abstract = str(
        paper.get("abstract", paper.get("content", "")) or ""
    ).strip()
    combined_text = normalize_text(f"{title}. {abstract}")

    signals = {group: [] for group in SIGNAL_ORDER}
    matched_phrases: Dict[str, List[str]] = {}

    for group in SIGNAL_ORDER:
        for signal, phrases in SIGNAL_GROUPS[group].items():
            matches = find_matching_phrases(combined_text, phrases)

            if matches:
                signals[group].append(signal)
                matched_phrases[signal] = matches

    evidence_tags = []

    for group, tag in TAG_BY_SIGNAL_GROUP.items():
        if group == "datasets":
            continue

        if signals[group] and tag not in evidence_tags:
            evidence_tags.append(tag)

    named_datasets = [
        signal
        for signal in signals["datasets"]
        if signal != "dataset_mentions"
    ]

    if named_datasets:
        evidence_tags.append("dataset")

    has_dataset_evidence = bool(named_datasets)
    has_evaluation_evidence = bool(signals["evaluation"])
    has_explicit_benchmark = bool(signals["benchmarks"])

    if (
        has_explicit_benchmark
        or (has_dataset_evidence and has_evaluation_evidence)
    ) and "benchmark" not in evidence_tags:
        evidence_tags.append("benchmark")

    return {
        "document_id": str(paper.get("document_id", "") or "").strip(),
        "title": title,
        "category": str(paper.get("category", "") or "").strip(),
        "evidence_tags": evidence_tags,
        "signals": signals,
        "matched_phrases": matched_phrases,
        "signal_snippets": build_signal_snippets(
            abstract,
            matched_phrases,
        ),
        "evidence_snippets": build_evidence_snippets(
            abstract,
            matched_phrases,
        ),
    }
