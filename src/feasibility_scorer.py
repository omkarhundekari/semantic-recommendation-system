from typing import Dict, List


DOMAIN_PROFILES = {
    "frontend": {
        "base": 6.7,
        "complexity": "Medium",
        "build_time": "5–8 days",
        "max_score": 8.2
    },
    "backend": {
        "base": 6.9,
        "complexity": "Medium",
        "build_time": "6–10 days",
        "max_score": 8.4
    },
    "full_stack": {
        "base": 7.0,
        "complexity": "Medium",
        "build_time": "7–12 days",
        "max_score": 8.5
    },
    "rag_llm": {
        "base": 7.3,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.8
    },
    "ai_ml": {
        "base": 7.1,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.6
    },
    "mlops": {
        "base": 7.2,
        "complexity": "High",
        "build_time": "9–15 days",
        "max_score": 8.7
    },
    "data_engineering": {
        "base": 7.0,
        "complexity": "Medium",
        "build_time": "7–12 days",
        "max_score": 8.4
    },
    "databases": {
        "base": 6.9,
        "complexity": "Medium",
        "build_time": "6–10 days",
        "max_score": 8.3
    },
    "cloud": {
        "base": 7.0,
        "complexity": "Medium",
        "build_time": "7–12 days",
        "max_score": 8.4
    },
    "devops": {
        "base": 7.0,
        "complexity": "Medium",
        "build_time": "7–12 days",
        "max_score": 8.4
    },
    "cybersecurity": {
        "base": 7.2,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.7
    },
    "blockchain": {
        "base": 7.0,
        "complexity": "High",
        "build_time": "9–16 days",
        "max_score": 8.5
    },
    "healthcare_ai": {
        "base": 7.1,
        "complexity": "High",
        "build_time": "9–16 days",
        "max_score": 8.6
    },
    "mobile": {
        "base": 6.8,
        "complexity": "Medium",
        "build_time": "6–10 days",
        "max_score": 8.2
    },
    "education_tech": {
        "base": 6.8,
        "complexity": "Medium",
        "build_time": "6–10 days",
        "max_score": 8.2
    },
    "recommendation_systems": {
        "base": 7.1,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.6
    },
    "nlp": {
        "base": 7.1,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.6
    },
    "computer_vision": {
        "base": 7.0,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.5
    },
    "fintech": {
        "base": 7.1,
        "complexity": "High",
        "build_time": "8–14 days",
        "max_score": 8.6
    },
    "developer_tools": {
        "base": 7.1,
        "complexity": "Medium",
        "build_time": "7–12 days",
        "max_score": 8.6
    },
    "general": {
        "base": 6.5,
        "complexity": "Medium",
        "build_time": "5–9 days",
        "max_score": 8.0
    }
}


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


GENERIC_STACK_TERMS = [
    "python",
    "fastapi",
    "streamlit",
    "postgresql",
    "docker",
    "react",
    "typescript",
    "tailwind css"
]


DEEP_TECH_TERMS = [
    "rag",
    "semantic search",
    "vector search",
    "embeddings",
    "llm evaluation",
    "faithfulness",
    "hallucination",
    "model registry",
    "drift detection",
    "experiment tracking",
    "data quality",
    "schema drift",
    "etl",
    "airflow",
    "query optimization",
    "indexing",
    "observability",
    "ci/cd",
    "kubernetes",
    "cloud cost",
    "risk scoring",
    "threat modeling",
    "security logs",
    "smart contracts",
    "computer vision",
    "ocr",
    "object detection",
    "fraud detection",
    "recommendation systems",
    "ranking",
    "personalization",
    "nlp",
    "text classification",
    "summarization",
    "github apis",
    "code analysis"
]


CAREER_SIGNAL_TERMS = [
    "engineer",
    "platform",
    "ml engineer",
    "ai engineer",
    "data engineer",
    "security engineer",
    "backend engineer",
    "frontend engineer",
    "cloud engineer",
    "devops engineer",
    "developer tools engineer",
    "computer vision engineer",
    "fintech engineer",
    "healthcare"
]


SCOPE_RISK_TERMS = [
    "clinical",
    "healthcare",
    "medication",
    "smart contract",
    "blockchain",
    "kubernetes",
    "multi-agent",
    "real-time",
    "distributed",
    "production",
    "fraud",
    "credit risk",
    "zero trust",
    "security",
    "object detection",
    "computer vision"
]


DEMO_CLARITY_TERMS = [
    "dashboard",
    "explain",
    "score",
    "rank",
    "monitor",
    "analyze",
    "recommend",
    "visualize",
    "extract",
    "detect",
    "track"
]



def build_project_profile(project_idea: Dict) -> Dict[str, str]:
    """
    Produces an explainable scope and effort estimate from the actual MVP,
    rather than relying only on a domain-level default.
    """
    title = str(project_idea.get("project_title", "")).lower()
    mvp_scope = project_idea.get("mvp_scope", [])
    advanced_extensions = project_idea.get("advanced_extensions", [])
    tech_stack = project_idea.get("suggested_tech_stack", [])

    mvp_text = " ".join(
        str(step) for step in mvp_scope
    ).lower()

    assessment_text = f"{title} {mvp_text}".lower()

    ambition_points = 0
    reasons = []

    if len(mvp_scope) >= 7:
        ambition_points += 1
        reasons.append("a larger MVP workflow")

    elif len(mvp_scope) >= 6:
        ambition_points += 1
        reasons.append("multiple MVP workflow stages")

    architecture_terms = [
        "source tree",
        "dependency map",
        "tightly coupled",
        "refactoring recommendations",
        "architecture-health report",
    ]

    if any(term in assessment_text for term in architecture_terms):
        ambition_points += 2
        reasons.append("component and dependency analysis")

    performance_terms = [
        "lighthouse", "web vitals", "bundle size",
        "performance metrics", "before-and-after"
    ]

    if any(term in assessment_text for term in performance_terms):
        ambition_points += 2
        reasons.append("performance measurement and diagnosis")

    quality_terms = [
        "accessibility", "design tokens",
        "consistency score", "component library"
    ]

    if any(term in assessment_text for term in quality_terms):
        ambition_points += 2
        reasons.append("design-quality and accessibility evaluation")

    ml_engineering_terms = [
        "baseline model",
        "classification dataset",
        "precision",
        "recall",
        "f1 score",
        "calibration",
        "error-slice",
        "prediction drift",
        "feature distributions",
        "feature contributions",
        "out-of-distribution",
    ]

    if any(term in assessment_text for term in ml_engineering_terms):
        ambition_points += 2
        reasons.append("ML evaluation, monitoring, or explainability work")

    if ambition_points >= 3:
        return {
            "scope": "Ambitious",
            "estimated_effort": "8–12 days",
            "reason": (
                "This project includes "
                + ", ".join(reasons[:3])
                + ". Start with one narrow analysis workflow before adding extensions."
            )
        }

    if ambition_points >= 2:
        return {
            "scope": "Moderate",
            "estimated_effort": "5–8 days",
            "reason": (
                "This project involves "
                + ", ".join(reasons[:3])
                + ". It is manageable as a focused MVP with constrained inputs."
            )
        }

    return {
        "scope": "Small",
        "estimated_effort": "3–5 days",
        "reason": (
            "This idea has a limited initial workflow and can be built as a focused prototype."
        )
    }


def score_project_feasibility(project_idea: Dict) -> Dict:
    domain = normalize_domain(project_idea.get("detected_domain", "general"))
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])

    text = collect_project_text(project_idea)

    score = profile["base"]
    score += score_evidence_grounding(project_idea)
    score += score_mvp_clarity(project_idea)
    score += score_technical_depth(text)
    score += score_career_signal(project_idea, text)
    score += score_demo_clarity(text)
    score += score_originality(text)
    score -= score_scope_risk(project_idea, text)

    score = apply_score_caps(score, domain, project_idea, text)
    score = apply_idea_level_adjustment(score, project_idea, domain, text)
    score = round(score, 1)

    complexity = estimate_complexity(project_idea, domain, text)
    build_time = estimate_build_time(domain, complexity)
    skill_signal = estimate_skill_signal(score, complexity, text)
    why = explain_score(project_idea, score, complexity, build_time, skill_signal)
    build_profile = build_project_profile(project_idea)

    return {
        "feasibility_score": score,
        "complexity": complexity,
        "estimated_build_time": build_time,
        "skill_signal": skill_signal,
        "why_worth_building": why,
        "build_profile": build_profile
    }


def normalize_domain(domain: str) -> str:
    if not domain:
        return "general"

    domain = str(domain).lower().strip()
    return DOMAIN_ALIASES.get(domain, domain)


def collect_project_text(project_idea: Dict) -> str:
    parts = []

    scalar_keys = [
        "project_title",
        "research_motivation",
        "idea_angle",
        "opportunity_area",
        "research_category",
        "detected_domain",
        "detected_intent",
        "evidence_source_type",
        "based_on_paper",
        "evidence_title"
    ]

    list_keys = [
        "mvp_scope",
        "advanced_extensions",
        "suggested_tech_stack",
        "resume_bullets",
        "target_roles",
        "extracted_themes",
        "extracted_skills"
    ]

    for key in scalar_keys:
        parts.append(str(project_idea.get(key, "")))

    for key in list_keys:
        value = project_idea.get(key, [])

        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        else:
            parts.append(str(value))

    return " ".join(parts).lower()


def score_evidence_grounding(project_idea: Dict) -> float:
    source_type = project_idea.get("evidence_source_type", "")
    evidence_title = project_idea.get("evidence_title", "")
    motivation = project_idea.get("research_motivation", "")

    score = 0.0

    if source_type == "research_paper":
        score += 0.35
    elif source_type == "project_pattern":
        score += 0.25
    elif source_type:
        score += 0.15

    if evidence_title:
        score += 0.15

    if isinstance(motivation, str) and len(motivation) > 180:
        score += 0.20
    elif isinstance(motivation, str) and len(motivation) > 80:
        score += 0.10

    return min(score, 0.55)


def score_mvp_clarity(project_idea: Dict) -> float:
    mvp = project_idea.get("mvp_scope", [])

    if not isinstance(mvp, list):
        return 0.0

    if len(mvp) >= 6:
        return 0.45

    if len(mvp) >= 4:
        return 0.30

    if len(mvp) >= 2:
        return 0.15

    return 0.0


def score_technical_depth(text: str) -> float:
    deep_matches = count_matches(text, DEEP_TECH_TERMS)
    generic_matches = count_matches(text, GENERIC_STACK_TERMS)

    score = 0.0

    if deep_matches >= 6:
        score += 0.85
    elif deep_matches >= 4:
        score += 0.65
    elif deep_matches >= 2:
        score += 0.40
    elif deep_matches >= 1:
        score += 0.20

    if generic_matches >= 4:
        score += 0.15
    elif generic_matches >= 2:
        score += 0.08

    return min(score, 0.90)


def score_career_signal(project_idea: Dict, text: str) -> float:
    roles = project_idea.get("target_roles", [])

    role_count = len(roles) if isinstance(roles, list) else 0
    role_term_matches = count_matches(text, CAREER_SIGNAL_TERMS)

    if role_count >= 4 and role_term_matches >= 3:
        return 0.45

    if role_count >= 3:
        return 0.35

    if role_count >= 2:
        return 0.25

    return 0.10


def score_demo_clarity(text: str) -> float:
    matches = count_matches(text, DEMO_CLARITY_TERMS)

    if matches >= 5:
        return 0.35

    if matches >= 3:
        return 0.25

    if matches >= 1:
        return 0.12

    return 0.0


def score_originality(text: str) -> float:
    originality_terms = [
        "intelligence",
        "assistant",
        "risk",
        "explain",
        "recommendation",
        "prioritization",
        "debugging",
        "evaluation",
        "lineage",
        "drift",
        "grounded",
        "monitoring"
    ]

    matches = count_matches(text, originality_terms)

    if matches >= 5:
        return 0.35

    if matches >= 3:
        return 0.25

    if matches >= 1:
        return 0.12

    return 0.0


def score_scope_risk(project_idea: Dict, text: str) -> float:
    domain = normalize_domain(project_idea.get("detected_domain", "general"))
    matches = count_matches(text, SCOPE_RISK_TERMS)

    penalty = 0.0

    if matches >= 5:
        penalty += 0.45
    elif matches >= 3:
        penalty += 0.30
    elif matches >= 1:
        penalty += 0.15

    high_risk_domains = [
        "healthcare_ai",
        "cybersecurity",
        "blockchain",
        "fintech",
        "computer_vision",
        "rag_llm",
        "mlops"
    ]

    if domain in high_risk_domains:
        penalty += 0.15

    if "clinical" in text or "medication" in text or "credit risk" in text:
        penalty += 0.20

    return min(penalty, 0.70)


def apply_score_caps(score: float, domain: str, project_idea: Dict, text: str) -> float:
    profile = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])
    max_score = profile["max_score"]

    deep_matches = count_matches(text, DEEP_TECH_TERMS)
    source_type = project_idea.get("evidence_source_type", "")

    if source_type != "research_paper" and deep_matches < 3:
        max_score = min(max_score, 8.1)

    if source_type != "research_paper" and domain in ["healthcare_ai", "fintech", "cybersecurity", "blockchain"]:
        max_score = min(max_score, 8.4)

    if domain in ["frontend", "mobile", "education_tech"] and deep_matches < 3:
        max_score = min(max_score, 8.0)

    score = min(score, max_score)
    score = max(score, 4.5)

    return score


def apply_idea_level_adjustment(
    score: float,
    project_idea: Dict,
    domain: str,
    text: str
) -> float:
    title = str(project_idea.get("project_title", "")).lower()
    angle = str(project_idea.get("idea_angle", "")).lower()
    combined = f"{title} {angle} {text}"

    easier_project_terms = [
        "receipt",
        "subscription spend",
        "habit tracker",
        "notes app",
        "learning path",
        "repository health",
        "dashboard",
        "tracker"
    ]

    complex_project_terms = [
        "construction safety",
        "object detection",
        "clinical",
        "medication",
        "credit risk",
        "fraud transaction",
        "smart contract",
        "zero trust",
        "model drift",
        "inference reliability",
        "multi-agent",
        "dependency mapper",
        "lineage"
    ]

    strong_demo_terms = [
        "risk scoring",
        "explain",
        "prioritization",
        "evaluation",
        "debugging",
        "monitoring",
        "optimization",
        "drift",
        "lineage",
        "anomaly"
    ]

    if any(term in combined for term in easier_project_terms):
        score -= 0.25

    if any(term in combined for term in complex_project_terms):
        score -= 0.10

    if any(term in combined for term in strong_demo_terms):
        score += 0.15

    if domain in ["healthcare_ai", "fintech", "cybersecurity", "blockchain"]:
        if any(term in combined for term in ["clinical", "medication", "credit risk", "fraud", "zero trust", "smart contract"]):
            score -= 0.15

    if domain == "computer_vision":
        if "ocr" in combined:
            score -= 0.20
        if "construction safety" in combined or "retail shelf" in combined:
            score += 0.05

    if domain == "developer_tools":
        if "repository health" in combined:
            score -= 0.20
        if "code review risk" in combined or "technical debt" in combined:
            score += 0.05

    return max(4.5, min(score, DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])["max_score"]))



def estimate_complexity(project_idea: Dict, domain: str, text: str) -> str:
    high_complexity_domains = [
        "rag_llm",
        "ai_ml",
        "mlops",
        "cybersecurity",
        "blockchain",
        "healthcare_ai",
        "recommendation_systems",
        "nlp",
        "computer_vision",
        "fintech"
    ]

    high_terms = [
        "rag",
        "llm",
        "drift",
        "model registry",
        "kubernetes",
        "security",
        "clinical",
        "medication",
        "smart contract",
        "fraud",
        "credit risk",
        "object detection",
        "computer vision",
        "distributed",
        "real-time"
    ]

    medium_terms = [
        "dashboard",
        "api",
        "postgresql",
        "docker",
        "monitor",
        "recommend",
        "score",
        "analyze",
        "sql",
        "react"
    ]

    high_matches = count_matches(text, high_terms)
    medium_matches = count_matches(text, medium_terms)

    title = str(project_idea.get("project_title", "")).lower()
    angle = str(project_idea.get("idea_angle", "")).lower()
    combined = f"{title} {angle} {text}"

    medium_override_terms = [
        "subscription spend",
        "repository health",
        "receipt",
        "learning path",
        "habit tracker",
        "notes app"
    ]

    high_override_terms = [
        "clinical",
        "medication",
        "healthcare risk",
        "readmission",
        "credit risk",
        "fraud transaction",
        "smart contract",
        "zero trust",
        "model drift",
        "inference reliability",
        "construction safety",
        "object detection",
        "lineage",
        "dependency"
    ]

    if any(term in combined for term in high_override_terms):
        return "High"

    if any(term in combined for term in medium_override_terms):
        return "Medium"

    if domain in ["healthcare_ai", "cybersecurity", "blockchain", "fintech"]:
        return "High"

    if domain in high_complexity_domains and high_matches >= 2:
        return "High"

    if high_matches >= 3:
        return "High"

    if medium_matches >= 3:
        return "Medium"

    return DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general"])["complexity"]


def estimate_build_time(domain: str, complexity: str) -> str:
    if complexity == "High":
        if domain in ["healthcare_ai", "blockchain", "cybersecurity", "fintech"]:
            return "10–16 days"
        if domain in ["rag_llm", "mlops", "computer_vision", "recommendation_systems"]:
            return "8–14 days"
        return "8–14 days"

    if complexity == "Medium":
        if domain in ["frontend", "mobile", "education_tech"]:
            return "5–8 days"
        if domain in ["backend", "databases"]:
            return "6–10 days"
        return "6–12 days"

    return "3–5 days"


def estimate_skill_signal(score: float, complexity: str, text: str) -> str:
    deep_matches = count_matches(text, DEEP_TECH_TERMS)

    if score >= 8.5 and complexity == "High" and deep_matches >= 5:
        return "Very Strong"

    if score >= 8.1 and deep_matches >= 3:
        return "Strong"

    if score >= 7.2:
        return "Strong"

    if score >= 6.2:
        return "Moderate"

    return "Basic"


def explain_score(
    project_idea: Dict,
    score: float,
    complexity: str,
    build_time: str,
    skill_signal: str
) -> str:
    title = project_idea.get("project_title", "This project")
    domain = normalize_domain(project_idea.get("detected_domain", "general"))
    source_type = project_idea.get("evidence_source_type", "evidence")
    roles = project_idea.get("target_roles", [])
    extracted_skills = project_idea.get("extracted_skills", [])
    tech_stack = project_idea.get("suggested_tech_stack", [])

    role_text = ", ".join(roles[:3]) if isinstance(roles, list) else str(roles)

    skill_candidates = []

    if isinstance(extracted_skills, list):
        skill_candidates.extend(extracted_skills)

    if isinstance(tech_stack, list):
        skill_candidates.extend(tech_stack)

    skill_candidates = list(dict.fromkeys(skill_candidates))
    skill_text = ", ".join(skill_candidates[:6]) if skill_candidates else "software engineering and project planning"

    source_label = str(source_type).replace("_", " ")

    return (
        f"{title} scores {score}/10 with a {skill_signal.lower()} career signal because it is grounded in "
        f"{source_label}, fits the {domain} domain, and demonstrates skills such as {skill_text}. "
        f"The estimated complexity is {complexity.lower()} with a build time of {build_time}. "
        f"The score is limited by implementation risk, scope size, and how clearly the project can be demonstrated for roles such as {role_text}."
    )


def count_matches(text: str, terms: List[str]) -> int:
    return sum(1 for term in terms if term.lower() in text)
