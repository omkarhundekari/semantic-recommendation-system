import re
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
)

from query_expander import get_query_metadata

if TYPE_CHECKING:
    from query_semantics import QuerySemanticSnapshot
from constraint_adapter import apply_constraints_to_idea
from project_intelligence import (
    build_project_intelligence,
    build_mvp_from_blueprint,
    build_advanced_features_from_blueprint,
    build_tech_stack_from_blueprint,
    build_target_roles_from_blueprint,
    augment_mvp_with_implementation_signals,
    augment_tech_stack_with_implementation_technologies
)


DOMAIN_RELEVANCE_TERMS = {
    "rag_llm": {
        "rag",
        "graphrag",
        "retrieval",
        "retriever",
        "generation",
        "llm",
        "language",
        "question",
        "answering",
        "grounding",
        "citation",
        "context",
        "evaluation",
        "hallucination",
    },
    "machine_learning": {
        "machine",
        "learning",
        "model",
        "prediction",
        "classification",
        "regression",
        "evaluation",
        "dataset",
        "feature",
    },
    "cloud_platform": {
        "cloud",
        "deployment",
        "container",
        "kubernetes",
        "docker",
        "aws",
        "monitoring",
        "observability",
        "infrastructure",
    },
    "cybersecurity": {
        "security",
        "cyber",
        "threat",
        "vulnerability",
        "attack",
        "incident",
        "log",
        "detection",
        "access",
    },
    "frontend": {
        "frontend",
        "react",
        "typescript",
        "interface",
        "dashboard",
        "ui",
        "ux",
        "web",
    },
}


def _meaningful_tokens(value: str) -> set:
    stop_words = {
        "and",
        "for",
        "from",
        "into",
        "that",
        "this",
        "with",
        "your",
        "build",
        "project",
        "system",
        "studio",
        "tool",
    }

    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in stop_words
    }


def _evidence_item_text(item: Dict) -> str:
    fields = [
        item.get("title", ""),
        item.get("category", ""),
        item.get("tags", ""),
        item.get("skills", ""),
        item.get("abstract", ""),
        item.get("content", ""),
        item.get("selection_reason", ""),
        item.get("architecture_signals", ""),
        item.get("technology_signals", ""),
    ]

    return " ".join(str(field) for field in fields)


def _relevance_score(
    item: Dict,
    planning_domain: str,
    project_title: str,
    idea_angle: str,
) -> int:
    item_tokens = _meaningful_tokens(_evidence_item_text(item))
    domain_tokens = DOMAIN_RELEVANCE_TERMS.get(
        planning_domain,
        set(),
    )
    project_tokens = _meaningful_tokens(
        f"{project_title} {idea_angle}"
    )

    domain_overlap = len(item_tokens & domain_tokens)
    project_overlap = len(item_tokens & project_tokens)

    return (domain_overlap * 4) + project_overlap


def select_evidence_for_focus(
    evidence_items: List[Dict],
    focus_type: str,
    fallback_index: int,
    planning_domain: str,
    project_title: str,
    idea_angle: str,
) -> Dict:
    """
    Selects evidence by domain and idea relevance first, then uses source
    preference only as a tie-breaker. This prevents unrelated project
    patterns from becoming the named inspiration for a generated idea.
    """
    if not evidence_items:
        return {}

    preferred_sources = {
        "buildable_gap": [
            "project_pattern",
            "github_repository",
            "research_paper",
        ],
        "implementation_architecture": [
            "github_repository",
            "project_pattern",
            "research_paper",
        ],
        "research_or_reliability_gap": [
            "research_paper",
            "github_repository",
            "project_pattern",
        ],
        "workflow_extension": [
            "project_pattern",
            "github_repository",
            "research_paper",
        ],
    }

    source_order = preferred_sources.get(
        focus_type,
        ["project_pattern", "github_repository", "research_paper"],
    )

    source_priority = {
        source_type: len(source_order) - index
        for index, source_type in enumerate(source_order)
    }

    scored_candidates = []

    for index, item in enumerate(evidence_items):
        relevance = _relevance_score(
            item=item,
            planning_domain=planning_domain,
            project_title=project_title,
            idea_angle=idea_angle,
        )

        if relevance <= 0:
            continue

        score = (relevance * 10) + source_priority.get(
            item.get("source_type", ""),
            0,
        )

        scored_candidates.append((score, -index, item))

    if scored_candidates:
        return max(scored_candidates, key=lambda candidate: candidate[:2])[2]

    for source_type in source_order:
        for item in evidence_items:
            if item.get("source_type") == source_type:
                return item

    return evidence_items[fallback_index % len(evidence_items)]


def generate_project_ideas(
    search_results: List[Dict],
    user_query: str,
    max_ideas: int = 3,
    constraints: Dict = None,
    detected_domain: str = None,
    semantic_snapshot: Optional[
        "QuerySemanticSnapshot"
    ] = None,
) -> List[Dict]:
    if not search_results:
        return []

    query_metadata = get_query_metadata(user_query)

    fallback_domain = query_metadata.get(
        "detected_domain",
        "general",
    )

    planning_domain = detected_domain or fallback_domain

    detected_intent = query_metadata.get(
        "detected_intent",
        "general",
    )

    intelligence = build_project_intelligence(
        evidence_items=search_results,
        user_query=user_query,
        detected_domain=planning_domain,
        max_ideas=max_ideas
    )

    blueprints = intelligence.get("idea_blueprints", [])
    ideas = []

    for index, blueprint in enumerate(blueprints[:max_ideas]):
        evidence_item = select_evidence_for_focus(
            evidence_items=search_results,
            focus_type=blueprint.get("evidence_focus_type", ""),
            fallback_index=index,
            planning_domain=planning_domain,
            project_title=blueprint.get("project_title", ""),
            idea_angle=blueprint.get("idea_angle", ""),
        )

        evidence_title = evidence_item.get("title", "Untitled Evidence Item")
        evidence_content = evidence_item.get(
            "abstract",
            evidence_item.get("content", "")
        )
        evidence_category = evidence_item.get("category", "general")
        source_type = evidence_item.get("source_type", "unknown")

        implementation_signals = split_csv_values(
            evidence_item.get("architecture_signals", "")
        )
        implementation_technologies = split_csv_values(
            evidence_item.get("technology_signals", "")
        )

        project_title = blueprint.get("project_title", "Untitled Project Idea")
        mvp_scope = build_mvp_from_blueprint(blueprint)
        advanced_extensions = build_advanced_features_from_blueprint(blueprint)
        tech_stack = build_tech_stack_from_blueprint(blueprint)
        target_roles = build_target_roles_from_blueprint(blueprint)

        if source_type == "github_repository":
            mvp_scope = augment_mvp_with_implementation_signals(
                mvp_scope,
                implementation_signals
            )
            tech_stack = augment_tech_stack_with_implementation_technologies(
                tech_stack,
                implementation_technologies
            )

        mvp_scope, advanced_extensions = apply_evidence_focus_to_roadmap(
            mvp_scope=mvp_scope,
            advanced_extensions=advanced_extensions,
            blueprint=blueprint
        )

        motivation = create_evidence_motivation(
            evidence_title=evidence_title,
            evidence_content=evidence_content,
            source_type=source_type,
            blueprint=blueprint,
            implementation_signals=implementation_signals,
            implementation_technologies=implementation_technologies
        )

        resume_bullets = create_resume_bullets(
            project_title=project_title,
            tech_stack=tech_stack,
            target_roles=target_roles
        )

        ideas.append({
            "project_title": project_title,
            "based_on_paper": evidence_title,
            "evidence_title": evidence_title,
            "evidence_url": evidence_item.get("url", ""),
            "evidence_source_type": source_type,
            "research_category": evidence_category,
            "implementation_signals": implementation_signals,
            "implementation_technologies": implementation_technologies,
            "github_selection_reason": evidence_item.get("selection_reason", ""),
            "detected_domain": blueprint.get(
                "detected_domain",
                planning_domain,
            ),
            "detected_intent": detected_intent,
            "idea_angle": blueprint.get("idea_angle", ""),
            "opportunity_area": blueprint.get("opportunity", ""),
            "evidence_focus_type": blueprint.get("evidence_focus_type", ""),
            "evidence_focus_statement": blueprint.get(
                "evidence_focus_statement",
                ""
            ),
            "evidence_driven_angle": blueprint.get(
                "evidence_driven_angle",
                ""
            ),
            "evidence_buildable_gap": blueprint.get(
                "evidence_buildable_gap",
                ""
            ),
            "evidence_project_opportunity": blueprint.get(
                "evidence_project_opportunity",
                ""
            ),
            "evidence_summary": blueprint.get("evidence_summary", ""),
            "evidence_confidence": blueprint.get(
                "evidence_confidence",
                {}
            ),
            "domain_relevant_technologies": blueprint.get(
                "domain_relevant_technologies",
                []
            ),
            "source_contributions": blueprint.get(
                "source_contributions",
                []
            ),
            "extracted_themes": blueprint.get("themes", []),
            "extracted_skills": blueprint.get("skills", []),
            "research_motivation": motivation,
            "mvp_scope": mvp_scope,
            "advanced_extensions": advanced_extensions,
            "suggested_tech_stack": tech_stack,
            "resume_bullets": resume_bullets,
            "target_roles": target_roles
        })

    return [
        apply_constraints_to_idea(idea, constraints or {})
        for idea in ideas
    ]


def apply_evidence_focus_to_roadmap(
    mvp_scope: List[str],
    advanced_extensions: List[str],
    blueprint: Dict
) -> tuple:
    """
    Adds one evidence-specific roadmap decision so each generated idea is
    meaningfully shaped by its distinct evidence focus.
    """
    focus_type = blueprint.get("evidence_focus_type", "")
    focus_statement = blueprint.get("evidence_focus_statement", "")
    updated_mvp = list(mvp_scope)
    updated_extensions = list(advanced_extensions)

    if focus_type == "buildable_gap":
        step = (
            "Define a measurable success metric that proves the project "
            "reduces the specific user problem identified in the evidence."
        )
        if step not in updated_mvp:
            updated_mvp.append(step)

    elif focus_type == "implementation_architecture":
        step = (
            "Document the core architecture boundaries and trace how data "
            "moves between the major implementation components."
        )
        if step not in updated_mvp:
            updated_mvp.append(step)

    elif focus_type == "research_or_reliability_gap":
        step = (
            "Add reliability checks, warning states, and evidence-based "
            "quality indicators for risky or low-confidence outputs."
        )
        if step not in updated_mvp:
            updated_mvp.append(step)

    elif focus_type == "workflow_extension":
        extension = (
            "Add a differentiated workflow extension based on the retrieved "
            "project-pattern evidence: "
            + focus_statement
        )
        if extension not in updated_extensions:
            updated_extensions.append(extension)

    return updated_mvp, updated_extensions



def create_evidence_motivation(
    evidence_title: str,
    evidence_content: str,
    source_type: str,
    blueprint: Dict,
    implementation_signals: List[str],
    implementation_technologies: List[str]
) -> str:
    clean_content = evidence_content[:320].replace("\n", " ") if evidence_content else ""
    project_title = blueprint.get("project_title", "this project")
    opportunity = blueprint.get("opportunity", "a practical software opportunity")
    idea_angle = blueprint.get("idea_angle", "")

    if source_type == "project_pattern":
        return (
            f"This idea is not a direct copy of the retrieved pattern. "
            f"It is inspired by the project pattern '{evidence_title}', which points toward "
            f"{opportunity}. The generated project '{project_title}' applies that direction as: "
            f"{idea_angle}"
        )

    if source_type == "github_repository":
        return (
            f"This idea uses '{evidence_title}' as a real implementation reference. "
            f"It informs a buildable direction for {opportunity}. "
            f"See the implementation-reference section below for the specific "
            f"architecture and technology signals."
        )

    if source_type == "research_paper":
        if clean_content:
            return (
                f"This idea is grounded in the research paper '{evidence_title}'. "
                f"The paper provides evidence related to: {clean_content}... "
                f"The generated project '{project_title}' turns that research direction into "
                f"a buildable software prototype focused on {opportunity}."
            )

        return (
            f"This idea is grounded in the research paper '{evidence_title}'. "
            f"The generated project '{project_title}' converts the research direction into "
            f"a buildable prototype focused on {opportunity}."
        )

    return (
        f"This idea is grounded in the retrieved evidence item '{evidence_title}'. "
        f"The generated project '{project_title}' uses that evidence to explore {opportunity}."
    )


def create_resume_bullets(
    project_title: str,
    tech_stack: List[str],
    target_roles: List[str]
) -> List[str]:
    stack_text = ", ".join(tech_stack[:6])
    role_text = ", ".join(target_roles[:3])
    article = get_article(project_title)

    return [
        f"Built {article} {project_title} that converts retrieved technical evidence into a buildable, career-aligned software project.",
        f"Implemented core workflows using {stack_text}, with emphasis on evidence grounding, project planning, and explainable recommendations.",
        f"Designed MVP scope, advanced extensions, skill mapping, and target-role alignment for roles such as {role_text}.",
        "Created a structured project intelligence pipeline covering evidence retrieval, idea generation, feasibility scoring, and resume-ready output."
    ]



def split_csv_values(value) -> List[str]:
    if not value:
        return []

    return [
        item.strip()
        for item in str(value).split(",")
        if item.strip()
    ]


def get_article(text: str) -> str:
    if not text:
        return "a"

    first_char = text.strip()[0].lower()

    if first_char in ["a", "e", "i", "o", "u"]:
        return "an"

    return "a"