import re
from typing import Any, Dict, List, Optional


SKILL_LEVELS = {
    "beginner",
    "intermediate",
    "advanced",
    "expert",
}


DIRECTION_HINTS = {
    "ai_ml": [
        "ai/ml",
        "machine learning",
        "ml engineer",
        "deep learning",
        "llm",
        "rag",
        "computer vision",
        "nlp",
    ],
    "software_engineering": [
        "react",
        "frontend",
        "backend",
        "full stack",
        "full-stack",
        "web app",
        "mobile app",
        "developer productivity",
        "developer tools",
        "software testing",
        "test automation",
        "flaky test",
        "debugging",
        "code changes",
        "root cause analysis",
        "code review",
        "repository",
    ],
    "cloud_platform": [
        "cloud",
        "devops",
        "aws",
        "azure",
        "gcp",
        "kubernetes",
        "infrastructure",
        "data engineering",
    ],
    "cybersecurity": [
        "cybersecurity",
        "security analyst",
        "security automation",
        "threat detection",
        "zero trust",
        "penetration testing",
    ],
    "blockchain": [
        "blockchain",
        "smart contract",
        "web3",
    ],
}


GENERIC_GOAL_PATTERNS = [
    "something useful for my resume",
    "something for my resume",
    "good project for my resume",
    "project for my resume",
    "something impressive",
    "good portfolio project",
    "project for my portfolio",
    "help me choose",
]


def clean_text(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def unique_items(items: List[str]) -> List[str]:
    seen = set()
    result = []

    for item in items:
        clean_item = clean_text(item)
        normalized_item = clean_item.lower()

        if clean_item and normalized_item not in seen:
            seen.add(normalized_item)
            result.append(clean_item)

    return result


def extract_role_hints(goal: str) -> List[str]:
    patterns = [
        r"\bfor (?:an?|the)\s+([a-z][a-z0-9 /&-]{1,60}?)\s+role\b",
        r"\btarget(?:ing)?\s+([a-z][a-z0-9 /&-]{1,60}?)\s+roles?\b",
        r"\bfor ([a-z][a-z0-9 /&-]{1,60}?)\s+jobs?\b",
    ]

    roles = []

    for pattern in patterns:
        matches = re.findall(pattern, goal, flags=re.IGNORECASE)

        for match in matches:
            role = clean_text(match)

            if role:
                roles.append(role)

    return unique_items(roles)


def extract_time_hint(goal: str) -> Optional[str]:
    patterns = [
        r"\b\d+\s*(?:day|days|week|weeks|month|months)\b",
        r"\bthis weekend\b",
        r"\bweekend\b",
        r"\bshort timeline\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, goal, flags=re.IGNORECASE)

        if match:
            return clean_text(match.group(0))

    return None


def extract_skill_hint(goal: str) -> Optional[str]:
    tokens = re.findall(r"[a-z]+", goal.lower())

    for token in tokens:
        if token in SKILL_LEVELS:
            return token

    return None


def detect_project_intent(goal: str) -> bool:
    project_signals = [
        "build",
        "create",
        "make",
        "develop",
        "project",
        "portfolio",
        "prototype",
        "mvp",
        "dashboard",
        "platform",
        "tool",
        "app",
    ]

    lowered_goal = goal.lower()

    return any(signal in lowered_goal for signal in project_signals)


def extract_direction_hints(goal: str) -> List[str]:
    lowered_goal = goal.lower()
    matched_families = []

    for family, phrases in DIRECTION_HINTS.items():
        if any(phrase in lowered_goal for phrase in phrases):
            matched_families.append(family)

    return unique_items(matched_families)


def is_generic_goal(goal: str) -> bool:
    lowered_goal = goal.lower()

    return any(
        pattern in lowered_goal
        for pattern in GENERIC_GOAL_PATTERNS
    )


def identify_ambiguity(
    goal: str,
    target_roles: List[str],
    time_available: Optional[str],
    preferred_stack: List[str],
    direction_hints: List[str],
) -> List[str]:
    signals = []

    if len(goal.split()) < 5:
        signals.append("goal_is_very_short")

    if not detect_project_intent(goal):
        signals.append("project_intent_is_unclear")

    if not target_roles:
        signals.append("target_role_is_missing")

    if not time_available:
        signals.append("time_constraint_is_missing")

    if not preferred_stack:
        signals.append("preferred_stack_is_missing")

    if not direction_hints:
        signals.append("technical_direction_is_missing")

    return signals


def is_purpose_only_project_goal(goal: str) -> bool:
    """
    Detect goals that express a desired outcome, such as a portfolio or
    resume project, without identifying a technical or domain direction.
    """
    generic_words = {
        "i",
        "want",
        "need",
        "would",
        "like",
        "to",
        "build",
        "make",
        "create",
        "a",
        "an",
        "the",
        "strong",
        "good",
        "great",
        "impressive",
        "best",
        "portfolio",
        "resume",
        "project",
        "projects",
        "app",
        "tool",
        "something",
        "for",
        "my",
        "me",
        "in",
    }

    meaningful_words = [
        word
        for word in re.findall(r"[a-z0-9]+", goal.lower())
        if word not in generic_words
    ]

    return len(meaningful_words) == 0


def should_clarify_before_retrieval(
    goal: str,
    target_roles: List[str],
    preferred_stack: List[str],
    direction_hints: List[str],
) -> bool:
    # A portfolio or resume objective is not itself a technical direction.
    # Ask before retrieval unless the user also supplied a role or stack.
    if (
        is_purpose_only_project_goal(goal)
        and not target_roles
        and not preferred_stack
    ):
        return True

    if target_roles or preferred_stack or direction_hints:
        return False

    if is_generic_goal(goal):
        return True

    return len(goal.split()) <= 5


def understand_query(
    goal: str,
    constraints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    constraints = constraints or {}

    cleaned_goal = clean_text(goal)

    explicit_roles = constraints.get("target_roles", [])
    explicit_stack = constraints.get("preferred_stack", [])
    explicit_time = clean_text(constraints.get("time_available"))
    explicit_skill = clean_text(constraints.get("skill_level"))

    target_roles = unique_items(
        list(explicit_roles) + extract_role_hints(cleaned_goal)
    )

    preferred_stack = unique_items(list(explicit_stack))

    time_available = explicit_time or extract_time_hint(cleaned_goal)
    skill_level = explicit_skill or extract_skill_hint(cleaned_goal)

    direction_hints = extract_direction_hints(cleaned_goal)

    ambiguity_signals = identify_ambiguity(
        goal=cleaned_goal,
        target_roles=target_roles,
        time_available=time_available,
        preferred_stack=preferred_stack,
        direction_hints=direction_hints,
    )

    requires_clarification_before_retrieval = (
        should_clarify_before_retrieval(
            goal=cleaned_goal,
            target_roles=target_roles,
            preferred_stack=preferred_stack,
            direction_hints=direction_hints,
        )
    )

    clarification_question = None
    clarification_options = []

    if requires_clarification_before_retrieval:
        clarification_question = (
            "What kind of work would you like this project to showcase?"
        )
        clarification_options = [
            "AI / ML",
            "Full-stack",
            "Cloud / Platform",
            "Cybersecurity",
            "Help me choose",
        ]

    return {
        "original_goal": goal,
        "cleaned_goal": cleaned_goal,
        "target_roles": target_roles,
        "preferred_stack": preferred_stack,
        "time_available": time_available,
        "skill_level": skill_level,
        "project_intent_detected": detect_project_intent(cleaned_goal),
        "direction_hints": direction_hints,
        "ambiguity_signals": ambiguity_signals,
        "requires_clarification_before_retrieval": (
            requires_clarification_before_retrieval
        ),
        "clarification_question": clarification_question,
        "clarification_options": clarification_options,
        "requires_evidence_inference": (
            not requires_clarification_before_retrieval
        ),
    }