from planning.semantic_diversification_repair import (
    build_semantic_diversification_repair_plan,
)


def candidate(title, score, workflow, mvp_scope):
    return {
        "title": title,
        "core_workflow": workflow,
        "mvp_scope": mvp_scope,
        "ranking": {"score": score},
    }


def test_returns_no_plan_when_candidates_are_semantically_distinct():
    plan = build_semantic_diversification_repair_plan(
        selected_candidates=[
            candidate(
                "Incident Timeline",
                0.91,
                ["Load events.", "Build a timeline."],
                ["Load data.", "Order records.", "Render timeline."],
            ),
            candidate(
                "Deployment Impact Explorer",
                0.88,
                ["Load releases.", "Compare health signals."],
                ["Load releases.", "Compare signals.", "Show impact."],
            ),
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "Incident Timeline",
                    "candidate_b_title": "Deployment Impact Explorer",
                    "raw_cosine": 0.61,
                }
            ]
        },
    )

    assert plan.status == "no_repair_needed"
    assert plan.directives == []
    assert plan.signals["replacement_count"] == 0


def test_keeps_higher_ranked_candidate_and_repairs_close_candidate():
    plan = build_semantic_diversification_repair_plan(
        selected_candidates=[
            candidate(
                "Pipeline Monitor",
                0.93,
                ["Run checks.", "Send alerts."],
                ["Load data.", "Run checks.", "Show alerts."],
            ),
            candidate(
                "Pipeline Failure Triage",
                0.84,
                ["Run checks.", "Review failures."],
                ["Load data.", "Run checks.", "Show failures."],
            ),
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "Pipeline Monitor",
                    "candidate_b_title": "Pipeline Failure Triage",
                    "raw_cosine": 0.7915,
                }
            ]
        },
    )

    assert plan.status == "repair_planned"
    assert plan.signals["close_cluster_count"] == 1
    assert plan.signals["replacement_count"] == 1

    directive = plan.directives[0]

    assert directive.replace_candidate_title == (
        "Pipeline Failure Triage"
    )
    assert directive.retain_candidate_titles == ["Pipeline Monitor"]
    assert directive.highest_pair_similarity == 0.7915
    assert directive.regeneration_brief["must_differ_from_titles"] == [
        "Pipeline Monitor"
    ]
    assert directive.regeneration_brief["avoid_retained_workflow"] == [
        "Run checks.",
        "Send alerts.",
    ]


def test_repairs_every_lower_ranked_candidate_in_close_cluster():
    plan = build_semantic_diversification_repair_plan(
        selected_candidates=[
            candidate(
                "Security Priority Service",
                0.95,
                ["Score exposure.", "Rank vulnerabilities."],
                ["Load findings.", "Score risk.", "Rank findings."],
            ),
            candidate(
                "Security Review Console",
                0.87,
                ["Review exposure.", "Rank vulnerabilities."],
                ["Load findings.", "Review risk.", "Rank findings."],
            ),
            candidate(
                "Exploitability Triage API",
                0.82,
                ["Score exploitability.", "Rank vulnerabilities."],
                ["Load findings.", "Score exploitability.", "Rank findings."],
            ),
        ],
        semantic_candidate_diversity={
            "pairwise_similarity": [
                {
                    "candidate_a_title": "Security Priority Service",
                    "candidate_b_title": "Security Review Console",
                    "raw_cosine": 0.79,
                },
                {
                    "candidate_a_title": "Security Review Console",
                    "candidate_b_title": "Exploitability Triage API",
                    "raw_cosine": 0.8105,
                },
            ]
        },
    )

    replacements = [
        directive.replace_candidate_title
        for directive in plan.directives
    ]

    assert plan.status == "repair_planned"
    assert plan.signals["close_cluster_count"] == 1
    assert replacements == [
        "Security Review Console",
        "Exploitability Triage API",
    ]
    assert all(
        directive.retain_candidate_titles == [
            "Security Priority Service"
        ]
        for directive in plan.directives
    )
