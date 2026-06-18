from embedding_search import search_papers
from project_idea_generator import generate_project_ideas
from feasibility_scorer import score_project_feasibility
from export_project_ideas import export_project_ideas_to_json


def main():
    query = "RAG systems for question answering"

    print(f"\nResearch Query: {query}\n")

    search_results = search_papers(query, top_k=3)

    project_ideas = generate_project_ideas(search_results, query)

    enriched_project_ideas = []

    for idx, idea in enumerate(project_ideas, start=1):
        feasibility = score_project_feasibility(idea)
        idea["feasibility_analysis"] = feasibility
        enriched_project_ideas.append(idea)

        print("=" * 80)
        print(f"PROJECT IDEA {idx}")
        print("=" * 80)

        print(f"\nTitle: {idea['project_title']}")
        print(f"\nBased on Paper: {idea['based_on_paper']}")
        print(f"\nResearch Category: {idea['research_category']}")

        print("\nResearch Motivation:")
        print(idea["research_motivation"])

        print("\nMVP Scope:")
        for item in idea["mvp_scope"]:
            print(f"- {item}")

        print("\nAdvanced Extensions:")
        for item in idea["advanced_extensions"]:
            print(f"- {item}")

        print("\nSuggested Tech Stack:")
        for item in idea["suggested_tech_stack"]:
            print(f"- {item}")

        print("\nResume Bullets:")
        for item in idea["resume_bullets"]:
            print(f"- {item}")

        print("\nTarget Roles:")
        for item in idea["target_roles"]:
            print(f"- {item}")

        print("\nFeasibility Analysis:")
        print(f"Score: {feasibility['feasibility_score']} / 10")
        print(f"Complexity: {feasibility['complexity']}")
        print(f"Estimated Build Time: {feasibility['estimated_build_time']}")
        print(f"Skill Signal: {feasibility['skill_signal']}")
        print(f"Why Worth Building: {feasibility['why_worth_building']}")

        print("\n")

    output_path = export_project_ideas_to_json(
        enriched_project_ideas,
        query
    )

    print("=" * 80)
    print("EXPORT COMPLETE")
    print("=" * 80)
    print(f"Project ideas saved to: {output_path}")


if __name__ == "__main__":
    main()