import re
from collections import Counter
from typing import Dict, List


RESEARCH_SIGNAL_MAP = {
    "methods": {
        "retrieval": ["retrieval", "retrieve", "retriever"],
        "reranking": ["reranking", "rerank"],
        "embeddings": ["embedding", "embeddings"],
        "knowledge_graphs": ["knowledge graph", "graph rag", "graph-based"],
        "classification": ["classification", "classifier"],
        "anomaly_detection": ["anomaly detection", "outlier detection"],
        "deep_learning": ["deep learning", "neural network", "transformer"],
        "computer_vision": ["object detection", "image classification", "computer vision"],
        "natural_language_processing": ["natural language processing", "nlp"],
        "explainability": ["explainability", "interpretable", "interpretability"],
    },
    "limitations": {
        "hallucination_risk": ["hallucination", "ungrounded"],
        "retrieval_quality": ["retrieval quality", "irrelevant context", "poor retrieval"],
        "citation_quality": ["citation", "attribution"],
        "evaluation_gap": ["evaluation gap", "lack of evaluation", "benchmark"],
        "data_quality": ["data quality", "missing data", "noisy data"],
        "latency_and_cost": ["latency", "cost", "resource intensive"],
        "fairness_and_bias": ["fairness", "bias", "biased"],
        "deployment_reliability": ["deployment", "reliability", "production"],
    },
    "applications": {
        "question_answering": ["question answering", "qa system"],
        "search_and_discovery": ["search", "discovery", "information retrieval"],
        "monitoring": ["monitoring", "observability", "drift"],
        "fraud_and_risk": ["fraud", "risk scoring", "transaction"],
        "cloud_optimization": ["cloud", "cost optimization", "resource optimization"],
        "healthcare": ["healthcare", "clinical", "medical", "patient"],
        "developer_productivity": ["developer", "code review", "repository"],
        "vision_workflows": ["image", "video", "object detection", "visual"],
    },
    "evaluation_clues": {
        "benchmarks": ["benchmark", "benchmarking"],
        "metrics": ["metric", "metrics", "precision", "recall", "f1"],
        "human_evaluation": ["human evaluation", "user study"],
        "experiments": ["experiment", "experimental"],
        "comparisons": ["comparison", "baseline", "ablation"],
    },
}


DOMAIN_OPPORTUNITY_PROFILES = {
    "rag_llm": {
        "problem": (
            "RAG applications can produce plausible answers even when retrieval, "
            "grounding, or citation quality is weak."
        ),
        "gap": (
            "Students and small teams need a practical way to inspect where a RAG "
            "pipeline is failing instead of treating it as a black box."
        ),
        "proposal": (
            "Build a RAG evaluation and debugging workbench that traces ingestion, "
            "chunking, retrieval, reranking, citations, and answer grounding."
        ),
    },
    "mlops": {
        "problem": (
            "ML teams often struggle to connect experiments, metrics, model versions, "
            "drift signals, and deployment readiness."
        ),
        "gap": (
            "Early-stage teams need a smaller, understandable monitoring workflow "
            "rather than a large enterprise MLOps platform."
        ),
        "proposal": (
            "Build an experiment and model-reliability dashboard that tracks runs, "
            "drift indicators, and release-readiness signals."
        ),
    },
    "cloud": {
        "problem": (
            "Cloud resources can accumulate cost, configuration risk, and monitoring "
            "gaps that are difficult to inspect together."
        ),
        "gap": (
            "Small teams need an understandable view of cloud cost-risk tradeoffs "
            "without adopting a full enterprise FinOps platform."
        ),
        "proposal": (
            "Build a cloud resource risk scanner that combines cost signals, "
            "configuration checks, and prioritized optimization recommendations."
        ),
    },
    "fintech": {
        "problem": (
            "Fraud and financial-risk systems need to balance detection quality, "
            "false positives, and understandable decisions."
        ),
        "gap": (
            "Many student projects predict fraud risk but do not explain why a "
            "transaction or customer was flagged."
        ),
        "proposal": (
            "Build an explainable fraud-risk dashboard with anomaly flags, reason "
            "codes, threshold comparison, and review-friendly decision summaries."
        ),
    },
    "healthcare_ai": {
        "problem": (
            "Healthcare AI outputs require careful interpretation, safety framing, "
            "and traceable evidence."
        ),
        "gap": (
            "Student prototypes often show predictions without separating model "
            "output, uncertainty, and caution notes."
        ),
        "proposal": (
            "Build a healthcare evidence assistant that presents model-style "
            "insights with confidence, limitations, and safe interpretation notes."
        ),
    },
    "computer_vision": {
        "problem": (
            "Computer-vision demos often show detections but provide limited support "
            "for reviewing confidence, errors, and system behavior."
        ),
        "gap": (
            "Students need a practical review workflow around detections rather than "
            "a one-time model inference demo."
        ),
        "proposal": (
            "Build a visual detection review dashboard with confidence thresholds, "
            "batch evaluation, and false-positive analysis."
        ),
    },
    "developer_tools": {
        "problem": (
            "Engineering teams accumulate repository, pull-request, and delivery "
            "signals that are hard to interpret together."
        ),
        "gap": (
            "Small teams need lightweight developer-productivity insights without "
            "building a full engineering analytics platform."
        ),
        "proposal": (
            "Build a repository intelligence dashboard that surfaces engineering "
            "activity, code-risk clues, and actionable workflow recommendations."
        ),
    },
}


DOMAIN_TECHNOLOGY_ALLOWLIST = {
    "rag_llm": {
        "Python", "JavaScript", "Docker", "FAISS", "Chroma", "Qdrant",
        "Neo4j", "PostgreSQL", "FastAPI", "React"
    },
    "mlops": {
        "Python", "Docker", "Kubernetes", "AWS", "PyTorch",
        "TensorFlow", "PostgreSQL", "GitHub Actions"
    },
    "cloud": {
        "Python", "Docker", "Kubernetes", "AWS", "JavaScript",
        "TypeScript", "PostgreSQL"
    },
    "fintech": {
        "Python", "TensorFlow", "PyTorch", "React", "Docker",
        "AWS", "PostgreSQL"
    },
    "healthcare_ai": {
        "Python", "PyTorch", "TensorFlow", "Docker", "PostgreSQL"
    },
    "computer_vision": {
        "Python", "PyTorch", "TensorFlow", "OpenCV", "Streamlit",
        "Docker"
    },
    "developer_tools": {
        "Python", "TypeScript", "JavaScript", "React", "Docker",
        "PostgreSQL", "GitHub Actions"
    },
}


def get_domain_relevant_technologies(
    technologies: List[str],
    detected_domain: str
) -> List[str]:
    allowed = DOMAIN_TECHNOLOGY_ALLOWLIST.get(detected_domain)

    if not allowed:
        return technologies

    return [
        technology
        for technology in technologies
        if technology in allowed
    ]



def split_csv_values(value) -> List[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


def dedupe(items: List[str], limit: int = 8) -> List[str]:
    seen = set()
    results = []

    for item in items:
        normalized = str(item).strip().lower()

        if normalized and normalized not in seen:
            seen.add(normalized)
            results.append(item)

        if len(results) >= limit:
            break

    return results


def get_item_text(item: Dict) -> str:
    fields = [
        item.get("title", ""),
        item.get("abstract", ""),
        item.get("content", ""),
        item.get("readme_excerpt", ""),
        item.get("tags", ""),
        item.get("selection_reason", ""),
    ]

    return " ".join(str(value) for value in fields).lower()


def extract_keyword_signals(
    text: str,
    signal_map: Dict[str, List[str]]
) -> List[str]:
    matches = []

    for signal, keywords in signal_map.items():
        if any(keyword in text for keyword in keywords):
            matches.append(signal)

    return matches


def format_signal(signal: str) -> str:
    return signal.replace("_", " ")


def build_evidence_confidence(
    source_counts: Dict[str, int],
    trusted_reference_count: int
) -> Dict[str, str]:
    has_research = source_counts.get("research_paper", 0) > 0
    has_patterns = source_counts.get("project_pattern", 0) > 0
    has_github = source_counts.get("github_repository", 0) > 0

    if has_research and has_patterns and trusted_reference_count > 0:
        return {
            "level": "high",
            "reason": (
                "The recommendation is supported by research evidence, a practical "
                "project pattern, and at least one trusted implementation reference."
            ),
        }

    if has_patterns and trusted_reference_count > 0:
        return {
            "level": "medium_high",
            "reason": (
                "The recommendation is supported by a practical project pattern and "
                "trusted implementation evidence, but not directly by research papers."
            ),
        }

    if has_research or has_patterns or has_github:
        return {
            "level": "medium",
            "reason": (
                "The recommendation has relevant evidence, but the available sources "
                "do not yet provide broad cross-source coverage."
            ),
        }

    return {
        "level": "low",
        "reason": "No usable supporting evidence was retrieved.",
    }


def build_project_opportunity(
    detected_domain: str,
    research_methods: List[str],
    research_limitations: List[str],
    implementation_components: List[str]
) -> Dict[str, str]:
    profile = DOMAIN_OPPORTUNITY_PROFILES.get(
        detected_domain,
        {
            "problem": (
                "Users need clearer ways to convert technical evidence into "
                "buildable software projects."
            ),
            "gap": (
                "Available evidence is often scattered across research, repositories, "
                "and generic project ideas."
            ),
            "proposal": (
                "Build an evidence-grounded project planning tool with a focused "
                "MVP and explainable recommendations."
            ),
        },
    )

    evidence_summary_parts = []

    if research_methods:
        evidence_summary_parts.append(
            "Research methods observed: "
            + ", ".join(format_signal(signal) for signal in research_methods[:3])
            + "."
        )

    if research_limitations:
        evidence_summary_parts.append(
            "Research concerns observed: "
            + ", ".join(format_signal(signal) for signal in research_limitations[:3])
            + "."
        )

    if implementation_components:
        evidence_summary_parts.append(
            "Implementation capabilities observed: "
            + ", ".join(
                format_signal(signal)
                for signal in implementation_components[:3]
            )
            + "."
        )

    return {
        "problem": profile["problem"],
        "buildable_gap": profile["gap"],
        "project_opportunity": profile["proposal"],
        "evidence_summary": " ".join(evidence_summary_parts)
        or "The opportunity is based on the retrieved multi-source evidence.",
    }


def build_evidence_intelligence(
    evidence_items: List[Dict],
    user_query: str,
    detected_domain: str
) -> Dict:
    source_counts = Counter()
    research_methods = []
    research_limitations = []
    research_applications = []
    research_evaluation = []

    implementation_components = []
    implementation_technologies = []
    deployment_clues = []
    trusted_references = []
    selection_reasons = []
    source_contributions = []

    workflow_clues = []
    pattern_skills = []
    target_roles = []
    pattern_titles = []

    for item in evidence_items:
        source_type = item.get("source_type", "unknown")
        source_counts[source_type] += 1

        item_text = get_item_text(item)

        if source_type == "research_paper":
            research_methods.extend(
                extract_keyword_signals(
                    item_text,
                    RESEARCH_SIGNAL_MAP["methods"],
                )
            )
            research_limitations.extend(
                extract_keyword_signals(
                    item_text,
                    RESEARCH_SIGNAL_MAP["limitations"],
                )
            )
            research_applications.extend(
                extract_keyword_signals(
                    item_text,
                    RESEARCH_SIGNAL_MAP["applications"],
                )
            )
            research_evaluation.extend(
                extract_keyword_signals(
                    item_text,
                    RESEARCH_SIGNAL_MAP["evaluation_clues"],
                )
            )

        elif source_type == "github_repository":
            architecture_signals = split_csv_values(
                item.get("architecture_signals", "")
            )
            technology_signals = split_csv_values(
                item.get("technology_signals", "")
            )

            source_contributions.append({
                "title": item.get("title", ""),
                "source_type": source_type,
                "architecture_signals": architecture_signals,
                "technology_signals": technology_signals,
                "trusted": (
                    item.get("trust_level")
                    == "approved_implementation_reference"
                ),
            })

            implementation_components.extend(architecture_signals)
            implementation_technologies.extend(technology_signals)

            deployment_clues.extend(
                signal
                for signal in architecture_signals
                if signal in {
                    "deployment_and_containers",
                    "cloud_and_serverless",
                    "evaluation_and_monitoring",
                }
            )

            if item.get("trust_level") == "approved_implementation_reference":
                trusted_references.append(item.get("title", ""))

            if item.get("selection_reason"):
                selection_reasons.append(item.get("selection_reason"))

        elif source_type == "project_pattern":
            pattern_titles.append(item.get("title", ""))
            workflow_clues.extend(split_csv_values(item.get("tags", "")))
            pattern_skills.extend(split_csv_values(item.get("skills", "")))
            target_roles.extend(split_csv_values(item.get("target_roles", "")))

    research_methods = dedupe(research_methods)
    research_limitations = dedupe(research_limitations)
    research_applications = dedupe(research_applications)
    research_evaluation = dedupe(research_evaluation)

    implementation_components = dedupe(implementation_components)
    implementation_technologies = dedupe(implementation_technologies)
    domain_relevant_technologies = get_domain_relevant_technologies(
        implementation_technologies,
        detected_domain,
    )
    deployment_clues = dedupe(deployment_clues)
    trusted_references = dedupe(trusted_references)
    selection_reasons = dedupe(selection_reasons, limit=4)

    workflow_clues = dedupe(workflow_clues)
    pattern_skills = dedupe(pattern_skills)
    target_roles = dedupe(target_roles)
    pattern_titles = dedupe(pattern_titles)

    opportunity = build_project_opportunity(
        detected_domain=detected_domain,
        research_methods=research_methods,
        research_limitations=research_limitations,
        implementation_components=implementation_components,
    )

    confidence = build_evidence_confidence(
        source_counts=dict(source_counts),
        trusted_reference_count=len(trusted_references),
    )

    return {
        "query": user_query,
        "detected_domain": detected_domain,
        "source_counts": dict(source_counts),
        "research_signals": {
            "methods": research_methods,
            "limitations": research_limitations,
            "applications": research_applications,
            "evaluation_clues": research_evaluation,
        },
        "implementation_signals": {
            "architecture_components": implementation_components,
            "observed_technologies": implementation_technologies,
            "domain_relevant_technologies": domain_relevant_technologies,
            "deployment_clues": deployment_clues,
            "trusted_references": trusted_references,
            "selection_reasons": selection_reasons,
            "source_contributions": source_contributions,
        },
        "project_pattern_signals": {
            "pattern_titles": pattern_titles,
            "workflow_clues": workflow_clues,
            "skills": pattern_skills,
            "target_roles": target_roles,
        },
        "project_opportunity": opportunity,
        "evidence_confidence": confidence,
    }
