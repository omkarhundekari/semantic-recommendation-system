import os
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from source_router import retrieve_evidence
from query_expander import get_query_metadata
from project_idea_generator import generate_project_ideas
from feasibility_scorer import score_project_feasibility
from export_project_ideas import export_project_ideas_to_json


st.set_page_config(
    page_title="Research-to-Prototype Intelligence Engine",
    page_icon="🚀",
    layout="wide"
)


def build_project_pipeline(query, top_k=6):
    query_metadata = get_query_metadata(query)
    corrected_query = query_metadata.get("corrected_query", query)

    if query_metadata.get("query_requires_confirmation"):
        return {
            "query": query,
            "corrected_query": corrected_query,
            "query_corrections": query_metadata.get("query_corrections", []),
            "query_status": "needs_correction_confirmation",
            "confirmation_message": (
                f"Did you mean: {corrected_query}?"
            ),
            "project_ideas": [],
            "retrieved_papers": [],
            "research_results": [],
            "project_results": [],
            "total_project_ideas": 0,
            "output_path": "",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    if query_metadata.get("detected_domain") == "general":
        return {
            "query": query,
            "corrected_query": corrected_query,
            "query_corrections": query_metadata.get("query_corrections", []),
            "query_status": "needs_clarification",
            "clarification_message": (
                "I could not confidently identify a supported technical topic "
                "from this query yet."
            ),
            "suggested_topics": [
                "RAG project ideas",
                "React portfolio projects",
                "Cloud cost optimization projects",
                "MLOps project ideas",
                "Cybersecurity automation projects",
                "Healthcare AI project ideas",
            ],
            "project_ideas": [],
            "retrieved_papers": [],
            "research_results": [],
            "project_results": [],
            "total_project_ideas": 0,
            "output_path": "",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    evidence_payload = retrieve_evidence(corrected_query, top_k=top_k)

    retrieved_evidence = evidence_payload["merged_results"]
    project_ideas = generate_project_ideas(retrieved_evidence, query)

    enriched_project_ideas = []

    for idea in project_ideas:
        feasibility = score_project_feasibility(idea)
        idea["feasibility_analysis"] = feasibility
        enriched_project_ideas.append(idea)

    output_path = export_project_ideas_to_json(enriched_project_ideas, query)

    return {
        "query": query,
        "corrected_query": corrected_query,
        "query_corrections": query_metadata.get("query_corrections", []),
        "query_status": "ready",
        "expanded_query": evidence_payload["expanded_query"],
        "detected_domain": evidence_payload["detected_domain"],
        "detected_intent": evidence_payload["detected_intent"],
        "selected_route": evidence_payload["selected_route"],
        "total_project_ideas": len(enriched_project_ideas),
        "retrieved_papers": retrieved_evidence,
        "research_results": evidence_payload["research_results"],
        "project_results": evidence_payload["project_results"],
        "project_ideas": enriched_project_ideas,
        "output_path": output_path,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def load_latest_output():
    outputs_dir = "outputs"

    if not os.path.exists(outputs_dir):
        return None

    json_files = [
        os.path.join(outputs_dir, file)
        for file in os.listdir(outputs_dir)
        if file.endswith(".json")
    ]

    if not json_files:
        return None

    latest_file = max(json_files, key=os.path.getmtime)

    with open(latest_file, "r", encoding="utf-8") as file:
        loaded_data = json.load(file)

    if isinstance(loaded_data, list):
        return {
            "query": "Loaded saved output",
            "expanded_query": "",
            "detected_domain": "unknown",
            "detected_intent": "unknown",
            "selected_route": "saved_output",
            "total_project_ideas": len(loaded_data),
            "retrieved_papers": [],
            "research_results": [],
            "project_results": [],
            "project_ideas": loaded_data,
            "output_path": latest_file,
            "generated_at": "Loaded from saved JSON"
        }

    return loaded_data


def render_header():
    st.title("🚀 Research-to-Prototype Intelligence Engine")

    st.markdown(
        """
        Convert research trends, software patterns, and technical ideas into buildable,
        resume-worthy project plans.
        """
    )

    st.markdown(
        """
        This system now uses **source routing**:
        research-heavy queries use the research corpus, project-style queries use the project corpus,
        and mixed queries can use both.
        """
    )


def render_sidebar():
    st.sidebar.header("Controls")

    load_latest = st.sidebar.button("Load Latest Saved Output")

    developer_view = st.sidebar.checkbox(
        "Developer / Evidence View",
        value=False,
        help=(
            "Show retrieval details, query routing, and analytics used to "
            "inspect the recommendation pipeline."
        )
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Test queries")
    st.sidebar.markdown(
        """
        - React projects  
        - RAG systems for question answering  
        - RAG project ideas  
        - AI automation projects  
        - Cybersecurity automation  
        - Healthcare AI  
        """
    )

    return load_latest, developer_view


def render_search_box():
    st.markdown("### What do you want to build or explore?")

    query = st.text_input(
        "Enter a topic, research area, or project direction",
        placeholder="Example: RAG project ideas, React projects, AI automation projects..."
    )

    generate_button = st.button("Generate Project Intelligence", type="primary")

    return query, generate_button


def render_summary_metrics(data):
    project_ideas = data.get("project_ideas", [])
    total_ideas = len(project_ideas)

    profile_counts = {}
    for idea in project_ideas:
        feasibility = idea.get("feasibility_analysis", {})
        profile = feasibility.get("build_profile", {})
        scope = profile.get("scope", "Unknown")
        profile_counts[scope] = profile_counts.get(scope, 0) + 1

    profile_order = ["Small", "Moderate", "Ambitious", "Unknown"]
    profile_summary = " · ".join(
        f"{count} {scope}"
        for scope in profile_order
        for count in [profile_counts.get(scope, 0)]
        if count
    ) or "Not available"

    route = str(data.get("selected_route", "unknown")).replace("_", " ").title()

    col1, col2, col3 = st.columns(3)
    col1.metric("Project Directions", total_ideas)
    col2.metric("Evidence Route", route)
    col3.metric("Build Profiles", profile_summary)


def render_query_understanding(data):
    with st.expander("View query understanding"):
        st.write("**Original query:**", data.get("query", ""))
        st.write("**Expanded query used for retrieval:**", data.get("expanded_query", ""))
        st.write("**Detected domain:**", data.get("detected_domain", "unknown"))
        st.write("**Detected intent:**", data.get("detected_intent", "unknown"))
        st.write("**Selected evidence route:**", data.get("selected_route", "unknown"))


def render_retrieved_papers(data):
    retrieved_evidence = data.get("retrieved_papers", [])

    if not retrieved_evidence:
        return

    st.header("Retrieved Evidence")
    st.markdown(
        "These are the strongest retrieved evidence items from the selected source route."
    )

    route = data.get("selected_route", "unknown")
    st.caption(f"Selected evidence route: {route}")

    evidence_rows = []

    for item in retrieved_evidence:
        evidence_rows.append({
            "Title": item.get("title", "Untitled"),
            "Category": item.get("category", "Unknown"),
            "Source Type": item.get("source_type", "unknown"),
            "Score": round(item.get("score", 0), 4),
            "URL": item.get("url", "")
        })

    evidence_df = pd.DataFrame(evidence_rows)
    st.dataframe(evidence_df, width="stretch")


def render_charts(data):
    project_ideas = data.get("project_ideas", [])
    retrieved_evidence = data.get("retrieved_papers", [])

    if not project_ideas:
        return

    st.header("Project Intelligence Analytics")

    st.markdown(
        "These analytics summarize why the generated ideas are useful: "
        "what evidence they came from, what skills they demonstrate, "
        "which roles they target, and how difficult they are to build."
    )

    render_idea_comparison_table(project_ideas)

    col1, col2 = st.columns(2)

    with col1:
        render_skill_coverage_chart(project_ideas)

    with col2:
        render_role_alignment_chart(project_ideas)

    col3, col4 = st.columns(2)

    with col3:
        render_evidence_mix_chart(retrieved_evidence)

    with col4:
        render_build_effort_chart(project_ideas)


def render_idea_comparison_table(project_ideas):
    st.subheader("Idea Comparison")

    rows = []

    for idea in project_ideas:
        feasibility = idea.get("feasibility_analysis", {})
        skills = idea.get("extracted_skills", idea.get("suggested_tech_stack", []))

        if isinstance(skills, list):
            top_skills = ", ".join(skills[:5])
        else:
            top_skills = str(skills)

        rows.append({
            "Project Idea": idea.get("project_title", "Untitled"),
            "Domain": idea.get("detected_domain", "unknown"),
            "Evidence Type": idea.get("evidence_source_type", "unknown"),
            "Score": feasibility.get("feasibility_score", "N/A"),
            "Complexity": feasibility.get("complexity", "Unknown"),
            "Build Time": feasibility.get("estimated_build_time", "Unknown"),
            "Skill Signal": feasibility.get("skill_signal", "Unknown"),
            "Top Skills": top_skills
        })

    comparison_df = pd.DataFrame(rows)
    st.dataframe(comparison_df, width="stretch")


def render_skill_coverage_chart(project_ideas):
    st.subheader("Skill Coverage")

    skill_counts = {}

    for idea in project_ideas:
        skills = idea.get("extracted_skills", [])

        if not skills:
            skills = idea.get("suggested_tech_stack", [])

        if isinstance(skills, str):
            skills = [skills]

        for skill in skills:
            clean_skill = str(skill).strip()

            if clean_skill:
                skill_counts[clean_skill] = skill_counts.get(clean_skill, 0) + 1

    if not skill_counts:
        st.info("No skill data available yet.")
        return

    skill_df = pd.DataFrame(
        sorted(
            skill_counts.items(),
            key=lambda item: item[1],
            reverse=True
        )[:12],
        columns=["Skill", "Coverage Count"]
    )

    st.dataframe(skill_df, width="stretch", hide_index=True)


def render_role_alignment_chart(project_ideas):
    st.subheader("Target Role Alignment")

    role_counts = {}

    for idea in project_ideas:
        roles = idea.get("target_roles", [])

        if isinstance(roles, str):
            roles = [roles]

        for role in roles:
            clean_role = str(role).strip()

            if clean_role:
                role_counts[clean_role] = role_counts.get(clean_role, 0) + 1

    if not role_counts:
        st.info("No role alignment data available yet.")
        return

    role_df = pd.DataFrame(
        sorted(
            role_counts.items(),
            key=lambda item: item[1],
            reverse=True
        )[:12],
        columns=["Target Role", "Alignment Count"]
    )

    st.dataframe(role_df, width="stretch", hide_index=True)


def render_evidence_mix_chart(retrieved_evidence):
    st.subheader("Evidence Source Mix")

    if not retrieved_evidence:
        st.info("No retrieved evidence available for this run.")
        return

    source_counts = {}

    for item in retrieved_evidence:
        source_type = item.get("source_type", "unknown")
        source_type = str(source_type).replace("_", " ").title()

        source_counts[source_type] = source_counts.get(source_type, 0) + 1

    source_df = pd.DataFrame(
        source_counts.items(),
        columns=["Evidence Source", "Count"]
    )

    st.bar_chart(source_df, x="Evidence Source", y="Count", width="stretch")


def render_build_effort_chart(project_ideas):
    st.subheader("Build Effort Summary")

    rows = []

    for idea in project_ideas:
        feasibility = idea.get("feasibility_analysis", {})

        rows.append({
            "Project": idea.get("project_title", "Untitled")[:35],
            "Score": feasibility.get("feasibility_score", 0),
            "Complexity": feasibility.get("complexity", "Unknown"),
            "Build Time": feasibility.get("estimated_build_time", "Unknown"),
            "Skill Signal": feasibility.get("skill_signal", "Unknown")
        })

    effort_df = pd.DataFrame(rows)

    if effort_df.empty:
        st.info("No build effort data available yet.")
        return

    st.bar_chart(effort_df, x="Project", y="Score", width="stretch")

    with st.expander("View build effort details"):
        st.dataframe(effort_df, width="stretch")


def render_project_ideas(data):
    project_ideas = data.get("project_ideas", [])

    if not project_ideas:
        return

    st.header("Generated Project Ideas")

    for index, idea in enumerate(project_ideas, start=1):
        feasibility = idea.get("feasibility_analysis", {})

        with st.container(border=True):
            st.subheader(f"Idea {index}: {idea.get('project_title', 'Untitled Project')}")

            col1, col2, col3 = st.columns(3)

            build_profile = feasibility.get("build_profile", {})

            col1.metric(
                "Scope",
                build_profile.get(
                    "scope",
                    feasibility.get("complexity", "Unknown")
                )
            )

            col2.metric(
                "Estimated Effort",
                build_profile.get(
                    "estimated_effort",
                    feasibility.get("estimated_build_time", "Unknown")
                )
            )

            col3.metric(
                "Career Signal",
                feasibility.get("skill_signal", "Unknown")
            )

            profile_reason = build_profile.get("reason", "")
            if profile_reason:
                st.caption(profile_reason)

            st.markdown("#### Why This Is Buildable")

            evidence_focus = idea.get("evidence_focus_statement", "")
            evidence_gap = idea.get("evidence_buildable_gap", "")
            evidence_confidence = idea.get("evidence_confidence", {})
            confidence_level = evidence_confidence.get("level", "unknown")
            confidence_reason = evidence_confidence.get("reason", "")

            if evidence_focus:
                st.markdown("**Evidence focus**")
                st.write(evidence_focus)

            if evidence_gap and evidence_gap.strip() != evidence_focus.strip():
                st.markdown("**Buildable gap**")
                st.write(evidence_gap)

            if confidence_reason:
                st.caption(
                    f"Evidence confidence: {confidence_level.replace('_', ' ').title()} "
                    f"— {confidence_reason}"
                )

            st.markdown("#### Based on Evidence")
            st.write(idea.get("based_on_paper", "Not available"))

            st.markdown("#### Research / Evidence Motivation")
            st.write(idea.get("research_motivation", "Not available"))

            if idea.get("evidence_source_type") == "github_repository":
                st.markdown("#### Implementation Reference")

                repository_name = idea.get(
                    "evidence_title",
                    "GitHub implementation reference"
                )
                repository_url = idea.get("evidence_url", "")

                if repository_url:
                    st.markdown(
                        f"**Repository:** [{repository_name}]({repository_url})"
                    )
                else:
                    st.markdown(f"**Repository:** {repository_name}")

                selection_reason = idea.get("github_selection_reason", "")
                if selection_reason:
                    st.markdown("**Why this reference was selected**")
                    st.write(selection_reason)

                implementation_signals = idea.get("implementation_signals", [])
                implementation_technologies = idea.get(
                    "implementation_technologies",
                    []
                )

                if implementation_signals:
                    st.markdown("**README-derived implementation signals**")
                    render_list(
                        [
                            signal.replace("_", " ").title()
                            for signal in implementation_signals
                        ]
                    )

                if implementation_technologies:
                    st.markdown("**Technologies observed in the reference**")
                    render_list(implementation_technologies)

                if implementation_signals or implementation_technologies:
                    st.caption(
                        "These repository signals were used as implementation "
                        "hints for the MVP scope and suggested technology stack."
                    )

            tab1, tab2, tab3, tab4, tab5 = st.tabs(
                [
                    "MVP Scope",
                    "Advanced Extensions",
                    "Tech Stack",
                    "Career Signal",
                    "Feasibility Reasoning"
                ]
            )

            with tab1:
                render_list(idea.get("mvp_scope", []))

            with tab2:
                render_list(idea.get("advanced_extensions", []))

            with tab3:
                render_list(idea.get("suggested_tech_stack", []))

            with tab4:
                st.markdown("**Target Roles**")
                render_list(idea.get("target_roles", []))

                st.markdown("**Resume Bullets**")
                render_list(idea.get("resume_bullets", []))

            with tab5:
                st.markdown("**Skill Signal**")
                st.write(feasibility.get("skill_signal", "Not available"))

                st.markdown("**Why Worth Building**")
                st.write(feasibility.get("why_worth_building", "Not available"))


def render_list(items):
    if not items:
        st.write("Not available")
        return

    if isinstance(items, str):
        st.write(items)
        return

    for item in items:
        st.markdown(f"- {item}")


def render_output_path(data):
    output_path = data.get("output_path")

    if output_path:
        st.success(f"Generated ideas saved to: {output_path}")


def main():
    render_header()

    load_latest, developer_view = render_sidebar()
    query, generate_button = render_search_box()

    if "pipeline_output" not in st.session_state:
        st.session_state.pipeline_output = None

    if load_latest:
        latest_output = load_latest_output()

        if latest_output:
            st.session_state.pipeline_output = latest_output
        else:
            st.warning("No saved JSON outputs found yet.")

    if generate_button:
        if not query.strip():
            st.warning("Enter a topic first.")
        else:
            with st.spinner("Retrieving evidence and generating project ideas..."):
                st.session_state.pipeline_output = build_project_pipeline(
                    query.strip()
                )

    data = st.session_state.pipeline_output

    if data:
        if data.get("query_status") == "needs_correction_confirmation":
            st.warning(
                data.get(
                    "confirmation_message",
                    "Please confirm the corrected query."
                )
            )

            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    "Yes, use corrected query",
                    type="primary",
                    key="confirm_corrected_query"
                ):
                    st.session_state.pipeline_output = build_project_pipeline(
                        data.get("corrected_query", "")
                    )
                    st.rerun()

            with col2:
                if st.button(
                    "No, I will edit my query",
                    key="reject_corrected_query"
                ):
                    st.session_state.pipeline_output = None
                    st.info(
                        "Edit the search text above and try again."
                    )

            return

        if data.get("query_status") == "needs_clarification":
            st.warning(data.get("clarification_message", "Please refine your query."))

            st.markdown("### Try one of these supported directions")
            for topic in data.get("suggested_topics", []):
                st.markdown(f"- {topic}")
            return

        corrections = data.get("query_corrections", [])
        if corrections:
            corrected_query = data.get("corrected_query", "")
            st.info(f"Using corrected query: **{corrected_query}**")

        render_summary_metrics(data)
        render_project_ideas(data)
        render_output_path(data)

        if developer_view:
            st.markdown("---")
            st.header("Developer / Evidence View")
            st.caption(
                "These diagnostics explain how the recommendation was retrieved "
                "and generated. They are not part of the main student workflow."
            )

            render_query_understanding(data)
            render_retrieved_papers(data)
            render_charts(data)
    else:
        st.info(
            "Enter a query to generate research-backed and project-grounded ideas."
        )


if __name__ == "__main__":
    main()