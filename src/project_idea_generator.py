from typing import Dict, List

from query_expander import get_query_metadata
from project_intelligence import (
    build_project_intelligence,
    build_mvp_from_blueprint,
    build_advanced_features_from_blueprint,
    build_tech_stack_from_blueprint,
    build_target_roles_from_blueprint,
    augment_mvp_with_implementation_signals,
    augment_tech_stack_with_implementation_technologies
)


def generate_project_ideas(
    search_results: List[Dict],
    user_query: str,
    max_ideas: int = 3
) -> List[Dict]:
    if not search_results:
        return []

    query_metadata = get_query_metadata(user_query)
    detected_domain = query_metadata.get("detected_domain", "general")
    detected_intent = query_metadata.get("detected_intent", "general")

    intelligence = build_project_intelligence(
        evidence_items=search_results,
        user_query=user_query,
        detected_domain=detected_domain,
        max_ideas=max_ideas
    )

    blueprints = intelligence.get("idea_blueprints", [])
    ideas = []

    for index, blueprint in enumerate(blueprints[:max_ideas]):
        evidence_item = search_results[index % len(search_results)]

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
            "detected_domain": detected_domain,
            "detected_intent": detected_intent,
            "idea_angle": blueprint.get("idea_angle", ""),
            "opportunity_area": blueprint.get("opportunity", ""),
            "extracted_themes": blueprint.get("themes", []),
            "extracted_skills": blueprint.get("skills", []),
            "research_motivation": motivation,
            "mvp_scope": mvp_scope,
            "advanced_extensions": advanced_extensions,
            "suggested_tech_stack": tech_stack,
            "resume_bullets": resume_bullets,
            "target_roles": target_roles
        })

    return ideas


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
        signal_text = ", ".join(
            signal.replace("_", " ")
            for signal in implementation_signals[:5]
        )

        technology_text = ", ".join(
            implementation_technologies[:6]
        )

        parts = [
            f"This idea uses '{evidence_title}' as a real implementation reference.",
            f"It informs a buildable direction for {opportunity}."
        ]

        if signal_text:
            parts.append(
                f"README-derived implementation signals include: {signal_text}."
            )

        if technology_text:
            parts.append(
                f"Relevant technology signals include: {technology_text}."
            )

        return " ".join(parts)

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