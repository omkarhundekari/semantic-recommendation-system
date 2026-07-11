from planning.mission_context import build_mission_context


def test_build_mission_context_preserves_dynamic_project_signals():
    context = build_mission_context(
        idea={
            "project_title": "AR VR Education Learning Explorer",
            "project_summary": "Build an immersive classroom prototype.",
            "detected_domain": "education_tech",
            "suggested_tech_stack": ["Python", "FastAPI", "React"],
            "mvp_scope": ["Create one AR VR learning flow."],
            "advanced_extensions": ["Add student feedback tracking."],
        },
        user_goal="AR VR education project",
        query="AR VR education project",
        resolved_planning_domain="education_tech",
        constraints={
            "skill_level": "intermediate",
            "time_available": "3 weeks",
            "preferred_stack": ["React", "Python"],
            "target_roles": ["Software Engineer"],
        },
        evidence_coverage={
            "coverage_state": "adequate_direct",
            "warnings": ["limited_direct_evidence"],
        },
    )

    assert context.project_title == "AR VR Education Learning Explorer"
    assert context.resolved_planning_domain == "education_tech"
    assert context.query_anchors[:3] == ["AR", "VR", "Education"]
    assert context.skill_level == "intermediate"
    assert context.timeline_bucket == "2_3_weeks"
    assert context.primary_stack[:3] == ["React", "Python", "FastAPI"]
    assert context.target_roles == ["Software Engineer"]
    assert context.evidence_coverage_state == "adequate_direct"
    assert context.mvp_steps == ["Create one AR VR learning flow."]
    assert context.warnings == ["limited_direct_evidence"]


def test_mission_context_falls_back_to_generic_playbook():
    context = build_mission_context(
        idea={
            "project_title": "Unknown Domain Build",
            "project_summary": "Build something unusual.",
            "detected_domain": "unknown_domain",
        },
        user_goal="unusual project",
        query="unusual project",
        resolved_planning_domain="unknown_domain",
        constraints={},
        evidence_coverage={},
    )

    assert context.playbook.domain == "generic"


def test_timeline_bucket_handles_one_week():
    context = build_mission_context(
        idea={
            "project_title": "Fast Build",
            "project_summary": "Build quickly.",
            "detected_domain": "generic",
        },
        user_goal="fast project",
        query="fast project",
        resolved_planning_domain="generic",
        constraints={"time_available": "1 week"},
        evidence_coverage={},
    )

    assert context.timeline_bucket == "1_week"


def test_mission_context_prefers_stack_terms_from_query_before_idea_stack():
    context = build_mission_context(
        idea={
            "project_title": "React Frontend Portfolio Frontend Experience",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        },
        user_goal="Build a React frontend portfolio project",
        query="Build a React frontend portfolio project",
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.primary_stack == ["React"]


def test_mission_context_detects_typescript_and_nextjs_aliases():
    context = build_mission_context(
        idea={
            "project_title": "Next Frontend Build",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python"],
        },
        user_goal="Build a NextJS frontend in TS",
        query="Build a NextJS frontend in TS",
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.primary_stack == ["Next.js", "TypeScript"]


def test_mission_context_keeps_idea_stack_when_query_has_no_stack_terms():
    context = build_mission_context(
        idea={
            "project_title": "Frontend Portfolio Experience",
            "project_summary": "Build a frontend portfolio workflow.",
            "detected_domain": "frontend",
            "suggested_tech_stack": ["Python", "FastAPI", "PostgreSQL"],
        },
        user_goal="Build a portfolio project",
        query="Build a portfolio project",
        resolved_planning_domain="frontend",
        constraints={},
        evidence_coverage={},
    )

    assert context.primary_stack[:3] == ["Python", "FastAPI", "PostgreSQL"]
