from typing import Any, Dict, List


FOCUS_TO_FAMILY: Dict[str, str] = {
    # AI / ML family
    "ai_ml": "ai_ml",
    "mlops": "ai_ml",
    "rag_llm": "ai_ml",
    "nlp": "ai_ml",
    "computer_vision": "ai_ml",
    "healthcare_ai": "ai_ml",
    "recommendation_systems": "ai_ml",

    # Software engineering family
    "frontend": "software_engineering",
    "backend": "software_engineering",
    "full_stack": "software_engineering",
    "developer_tools": "software_engineering",
    "mobile": "software_engineering",

    # Cloud / platform family
    "cloud": "cloud_platform",
    "devops": "cloud_platform",
    "data_engineering": "cloud_platform",
    "databases": "cloud_platform",

    # Standalone families
    "cybersecurity": "cybersecurity",
    "blockchain": "blockchain",
    "fintech": "fintech",
    "education_tech": "education_tech",
}


CATEGORY_TO_FOCUS: Dict[str, str] = {
    # arXiv categories
    "cs.ai": "ai_ml",
    "cs.lg": "ai_ml",
    "cs.cl": "nlp",
    "cs.cv": "computer_vision",
    "cs.ir": "recommendation_systems",
    "cs.se": "developer_tools",
    "cs.cr": "cybersecurity",

    # Internal corpus categories
    "ai_ml": "ai_ml",
    "machine_learning": "ai_ml",
    "machine learning": "ai_ml",
    "mlops": "mlops",
    "rag_llm": "rag_llm",
    "nlp": "nlp",
    "computer_vision": "computer_vision",
    "recommendation_systems": "recommendation_systems",
    "healthcare_ai": "healthcare_ai",

    "frontend": "frontend",
    "backend": "backend",
    "full_stack": "full_stack",
    "developer_tools": "developer_tools",
    "mobile": "mobile",

    "cloud": "cloud",
    "devops": "devops",
    "data_engineering": "data_engineering",
    "databases": "databases",

    "cybersecurity": "cybersecurity",
    "security": "cybersecurity",
    "blockchain": "blockchain",
    "fintech": "fintech",
    "education_tech": "education_tech",
}


def normalize_value(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("-", "_")
    )


def get_domain_family(focus: str) -> str:
    normalized_focus = normalize_value(focus)

    return FOCUS_TO_FAMILY.get(normalized_focus, "general")


def get_focus_from_category(category: Any) -> str:
    normalized_category = normalize_value(category)

    return CATEGORY_TO_FOCUS.get(normalized_category, "general")


def get_family_focuses(family: str) -> List[str]:
    normalized_family = normalize_value(family)

    return sorted(
        focus
        for focus, mapped_family in FOCUS_TO_FAMILY.items()
        if mapped_family == normalized_family
    )


def is_focus_in_family(focus: str, family: str) -> bool:
    return get_domain_family(focus) == normalize_value(family)