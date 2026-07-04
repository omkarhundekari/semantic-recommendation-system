from product_plan_readiness import assess_product_plan_readiness


def make_ideas():
    return [
        {
            "feasibility_analysis": {
                "build_profile": {"difficulty": "Easy"}
            }
        },
        {
            "feasibility_analysis": {
                "build_profile": {"difficulty": "Medium"}
            }
        },
        {
            "feasibility_analysis": {
                "build_profile": {"difficulty": "Hard"}
            }
        },
    ]


def make_verification_results():
    return [
        {
            "status": "passed",
            "checks": {
                "evidence_present": True,
                "no_banned_stack": True,
            },
            "warnings": [],
        }
        for _ in range(3)
    ]


def test_marks_complete_verified_plan_ready():
    result = assess_product_plan_readiness(
        evidence_items=[
            {
                "source_type": "research_paper",
                "title": "Evidence One",
            },
            {
                "source_type": "github_repository",
                "title": "Evidence Two",
            },
        ],
        ideas=make_ideas(),
        verification_results=make_verification_results(),
        repairs_by_index=[[], [], []],
        research_evidence_assessment={
            "confidence": {
                "level": "strong",
                "reason": "Multiple direct papers support the query.",
            },
            "evidence": {
                "alignment_summary": {
                    "direct": 3,
                    "adjacent": 0,
                    "weak": 0,
                }
            },
        },
    )

    assert result.status == "ready"
    assert result.signals["focused_evidence_count"] == 2
    assert result.signals["portfolio_difficulties"] == [
        "Easy",
        "Medium",
        "Hard",
    ]


def test_marks_limited_research_plan_for_review():
    verification_results = make_verification_results()
    verification_results[1]["warnings"] = [
        "The preferred technology stack is not reflected."
    ]

    result = assess_product_plan_readiness(
        evidence_items=[
            {
                "source_type": "research_paper",
                "title": "Evidence One",
            }
        ],
        ideas=make_ideas(),
        verification_results=verification_results,
        repairs_by_index=[[], [], []],
        research_evidence_assessment={
            "confidence": {
                "level": "limited",
                "reason": "Only one matching paper was available.",
            },
            "evidence": {
                "alignment_summary": {
                    "direct": 1,
                    "adjacent": 0,
                    "weak": 0,
                }
            },
        },
    )

    assert result.status == "needs_review"
    assert "1 final verification warning(s) remain." in result.reasons
    assert (
        "Research evidence is limited, so the plan should be reviewed "
        "with its source context."
        in result.reasons
    )


def test_blocks_plan_with_missing_visible_evidence():
    verification_results = make_verification_results()
    verification_results[2]["checks"]["evidence_present"] = False

    result = assess_product_plan_readiness(
        evidence_items=[
            {
                "source_type": "project_pattern",
                "title": "Evidence One",
            }
        ],
        ideas=make_ideas(),
        verification_results=verification_results,
        repairs_by_index=[[], [], []],
    )

    assert result.status == "blocked"
    assert (
        "At least one direction is missing a visible evidence reference."
        in result.reasons
    )
