from product_api import (
    build_research_evidence_assessment,
    generate_project_intelligence,
)
from schemas.product_models import ProjectIntelligenceRequest


def test_builds_api_assessment_from_focused_research_results():
    evidence_payload = {
        "research_results": [
            {
                "document_id": "arxiv:1111.11111",
                "title": "Retrieval-Augmented Generation for Question Answering",
                "abstract": (
                    "We improve retrieval augmented generation for "
                    "question answering with a retrieval method."
                ),
                "category": "cs.IR",
                "retrieval_rank": 1,
            },
            {
                "document_id": "arxiv:2222.22222",
                "title": "RAG Evaluation for Question Answering",
                "abstract": (
                    "We evaluate retrieval augmented generation systems "
                    "for question answering."
                ),
                "category": "cs.IR",
                "retrieval_rank": 2,
            },
            {
                "document_id": "arxiv:3333.33333",
                "title": "Practical RAG Applications",
                "abstract": (
                    "We study retrieval augmented generation applications "
                    "for question answering."
                ),
                "category": "cs.IR",
                "retrieval_rank": 3,
            },
        ]
    }

    result = build_research_evidence_assessment(
        evidence_payload,
        query="retrieval augmented generation for question answering",
    )

    assert result["confidence"]["level"] == "strong"
    assert result["evidence"]["alignment_summary"]["direct"] == 3


def test_returns_none_when_no_research_results_exist():
    assert build_research_evidence_assessment(
        {"research_results": []},
        query="cloud cost optimization",
    ) is None


def test_response_schema_accepts_optional_research_evidence_assessment():
    from schemas.product_models import ProjectIntelligenceResponse

    response = ProjectIntelligenceResponse(
        status="ready",
        query="rag project",
        goal_summary="rag project",
        research_evidence_assessment={
            "confidence": {
                "level": "strong",
            },
        },
        resolved_planning_domain="rag_llm",
    )

    assert response.research_evidence_assessment["confidence"]["level"] == "strong"
    assert response.resolved_planning_domain == "rag_llm"


def test_api_assessment_uses_registered_required_anchors():
    evidence_payload = {
        "research_results": [
            {
                "document_id": "arxiv:4444.44444",
                "title": "Retrieval-Augmented Generation for Question Answering",
                "abstract": (
                    "We improve retrieval augmented generation for "
                    "question answering with a retrieval method."
                ),
                "category": "cs.IR",
                "retrieval_rank": 1,
            }
        ]
    }

    result = build_research_evidence_assessment(
        evidence_payload,
        query=(
            "Build a retrieval augmented generation project "
            "for question answering"
        ),
    )

    assert result["required_anchor_terms"] == [
        "retrieval augmented generation",
        "question answering",
    ]

def test_ready_api_response_exposes_resolved_rag_planning_domain():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    assert response.status == "ready"
    assert response.inferred_focus == "ai_ml"
    assert response.resolved_planning_domain == "rag_llm"

    assert len(response.directions) == 3
    assert all(
        direction.decision_trace is not None
        for direction in response.directions
    )
    assert all(
        direction.decision_trace.planning_domain == "rag_llm"
        for direction in response.directions
    )

    assert response.product_plan_readiness is not None
    assert response.product_plan_readiness["status"] in {
        "ready",
        "needs_review",
        "blocked",
    }
    assert response.product_plan_readiness["signals"]["direction_count"] == 3
    assert response.product_plan_readiness["signals"][
        "portfolio_difficulties"
    ] == ["Easy", "Medium", "Hard"]


def test_ready_api_response_exposes_synthesis_status_without_raw_llm_output():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    assert response.status == "ready"
    assert response.synthesis_status is not None
    assert response.synthesis_status.available is False
    assert (
        response.synthesis_status.safe_inspection_endpoint
        == "/v1/synthesis-demo"
    )
    assert (
        response.synthesis_status.current_planning_source
        == "deterministic_product_pipeline"
    )
    assert response.synthesis_status.reason == (
        "live_synthesis_execution_not_enabled_for_project_intelligence"
    )

    summary = response.synthesis_status.synthesis_summary
    assert summary.status == "preview_valid"
    assert summary.source == "deterministic_fallback_preview"
    assert isinstance(summary.can_run_llm, bool)
    assert summary.routing_reason
    assert summary.card_count > 0
    assert summary.validated is True
    assert summary.grounded_direction_count == 3
    assert summary.invented_source_count == 0
    assert summary.estimated_tokens > 0

    live_cards = response.synthesis_status.live_evidence_cards
    assert live_cards["card_count"] > 0
    assert live_cards["query_aligned_card_count"] >= 0
    assert {
        "strong_count",
        "limited_count",
        "exploratory_count",
        "weak_card_count",
        "suspicious_card_count",
    }.issubset(live_cards)

    routing_preview = response.synthesis_status.routing_preview
    assert "should_route" in routing_preview
    assert "reason" in routing_preview
    assert routing_preview["mode"] == "deep"

    token_estimate = response.synthesis_status.token_estimate
    assert token_estimate["estimated_tokens"] > 0
    assert "evidence_cards" in token_estimate["section_token_estimates"]

    preview = response.synthesis_status.live_final_synthesis_preview
    assert preview["source"] == "deterministic_fallback_preview"
    assert preview["fallback_used"] is True

    parsed_preview = preview["parsed_response"]
    assert parsed_preview["synthesis_source"] == (
        "deterministic_fallback_preview"
    )
    assert len(parsed_preview["project_directions"]) == 3
    assert all(
        direction["source_ids"]
        for direction in parsed_preview["project_directions"]
    )

    preview_validation = (
        response.synthesis_status.live_final_synthesis_preview_validation
    )
    assert preview_validation["is_valid"] is True
    assert preview_validation["output_path"] == (
        "live_final_synthesis_preview"
    )
    assert preview_validation["invented_source_ids"] == ()
    assert preview_validation["failure_categories"] == ()
    assert all(
        trace["is_grounded"]
        for trace in preview_validation["direction_grounding_traces"]
    )

    assert response.synthesis_status.safety_pipeline == {
        "raw_output_validation": True,
        "deterministic_fallback": True,
        "final_synthesis_validation": True,
    }


def test_project_intelligence_synthesis_status_serializes_for_frontend():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    payload = response.model_dump()

    synthesis_status = payload["synthesis_status"]

    assert synthesis_status["available"] is False
    assert synthesis_status["synthesis_summary"]["status"] == "preview_valid"
    assert synthesis_status["synthesis_summary"]["validated"] is True
    assert synthesis_status["synthesis_summary"][
        "grounded_direction_count"
    ] == 3
    assert synthesis_status["synthesis_summary"][
        "invented_source_count"
    ] == 0

    preview = synthesis_status["live_final_synthesis_preview"]
    assert preview["source"] == "deterministic_fallback_preview"
    assert preview["fallback_used"] is True
    assert len(preview["parsed_response"]["project_directions"]) == 3

    validation = synthesis_status[
        "live_final_synthesis_preview_validation"
    ]
    assert validation["is_valid"] is True
    assert validation["invented_source_ids"] == ()
    assert validation["failure_categories"] == ()


def test_project_intelligence_synthesis_status_contract_keys():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    synthesis_status = response.model_dump()["synthesis_status"]

    assert set(synthesis_status) == {
        "available",
        "reason",
        "safe_inspection_endpoint",
        "current_planning_source",
        "synthesis_summary",
        "validated_project_directions",
        "presentation_project_directions",
        "frontend_project_directions",
        "live_evidence_cards",
        "routing_preview",
        "token_estimate",
        "live_final_synthesis_preview",
        "live_final_synthesis_preview_validation",
        "safety_pipeline",
    }

    assert set(synthesis_status["synthesis_summary"]) == {
        "status",
        "source",
        "can_run_llm",
        "routing_reason",
        "card_count",
        "validated",
        "grounded_direction_count",
        "invented_source_count",
        "estimated_tokens",
    }

    validated_directions = synthesis_status["validated_project_directions"]
    assert len(validated_directions) == 3
    assert set(validated_directions[0]) == {
        "scope_level",
        "build_type",
        "estimated_time",
        "title",
        "evidence_confidence",
        "source_ids",
        "grounding_warnings",
    }

    presentation_directions = synthesis_status[
        "presentation_project_directions"
    ]
    assert len(presentation_directions) == 3
    assert set(presentation_directions[0]) == {
        "title",
        "level",
        "estimated_time",
        "what_you_will_build",
        "why_it_matters",
        "skills_shown",
        "interview_talking_point",
        "evidence_badge",
        "confidence_explanation",
        "open_questions",
        "evidence_summary",
    }
    assert "source_ids" not in presentation_directions[0]


def test_synthesis_summary_marks_invalid_preview_when_sources_are_invented():
    from types import SimpleNamespace

    from planning.evidence_cards import EvidenceCard
    from planning.llm_synthesis_output_validator import (
        validate_synthesis_parsed_response_against_cards,
    )
    from planning.product_synthesis_status import build_synthesis_summary

    evidence_cards = [
        EvidenceCard(
            source_id="known-source",
            source_type="research_paper",
            title="Known Source",
            support_scope="direct",
            evidence_confidence="Strong",
            key_excerpt="Known grounded evidence.",
            specific_method_or_technique=None,
            specific_dataset_or_benchmark=None,
            specific_implementation_signal=None,
            grounding_warning=None,
            relevance_signal="plausible",
            relevance_statuses=("lexically_supported",),
            linked_candidate_titles=(),
            user_facing_explanation="Grounded source.",
        )
    ]

    parsed_response = {
        "project_directions": [
            {
                "scope_level": "easy",
                "build_type": "quick_build",
                "estimated_time": "1-2 days",
                "title": "Invented Easy Direction",
                "source_ids": ["invented-source"],
                "evidence_confidence": "Strong",
                "grounding_warnings": [],
                "resume_bullet": "Built an invented-source feature.",
            },
            {
                "scope_level": "medium",
                "build_type": "resume_mvp",
                "estimated_time": "3-5 days",
                "title": "Invented MVP Direction",
                "source_ids": ["invented-source"],
                "evidence_confidence": "Strong",
                "grounding_warnings": [],
                "resume_bullet": "Built an invented-source MVP.",
            },
            {
                "scope_level": "hard",
                "build_type": "flagship_extension",
                "estimated_time": "1-2 weeks",
                "title": "Invented Flagship Direction",
                "source_ids": ["invented-source"],
                "evidence_confidence": "Strong",
                "grounding_warnings": [],
                "resume_bullet": "Built an invented-source flagship.",
            },
        ],
        "overall_confidence": "Strong",
        "assumptions": [],
        "warnings": [],
    }

    preview_validation = validate_synthesis_parsed_response_against_cards(
        parsed_response=parsed_response,
        evidence_cards=evidence_cards,
    )

    summary = build_synthesis_summary(
        routing_decision=SimpleNamespace(
            should_route=True,
            reason="routing_approved",
        ),
        token_estimate=SimpleNamespace(estimated_tokens=1234),
        evidence_cards=evidence_cards,
        preview_validation=preview_validation,
    )

    assert preview_validation.is_valid is False
    assert preview_validation.invented_source_ids == ("invented-source",)
    assert summary == {
        "status": "preview_invalid",
        "source": "deterministic_fallback_preview",
        "can_run_llm": True,
        "routing_reason": "routing_approved",
        "card_count": 1,
        "validated": False,
        "grounded_direction_count": 0,
        "invented_source_count": 1,
        "estimated_tokens": 1234,
    }


def test_frontend_project_directions_use_ready_direction_titles():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal=(
                "Build a retrieval augmented generation project for "
                "question answering for ML engineer roles in 3 weeks"
            ),
            selected_direction="AI / ML",
        )
    )

    payload = response.model_dump()
    ready_titles = [
        direction["title"]
        for direction in payload["directions"]
    ]
    frontend_titles = [
        direction["title"]
        for direction in payload["synthesis_status"][
            "frontend_project_directions"
        ]
    ]

    assert frontend_titles == ready_titles


def test_multidomain_clear_queries_resolve_without_clarification():
    cases = [
        ("React portfolio project for frontend roles", "frontend"),
        ("DevOps observability dashboard project", "devops"),
        ("FinTech fraud detection project", "fintech"),
        ("MLOps experiment tracking project", "mlops"),
    ]

    for goal, expected_focus in cases:
        response = generate_project_intelligence(
            ProjectIntelligenceRequest(
                goal=goal,
                constraints={
                    "skill_level": "intermediate",
                    "time_available": "3 weeks",
                    "target_roles": ["Software Engineer"],
                    "preferred_stack": ["Python", "FastAPI", "React"],
                },
            )
        )

        payload = response.model_dump()

        assert payload["status"] == "ready", goal
        assert payload["resolved_planning_domain"] == expected_focus, goal
        assert len(
            payload["synthesis_status"]["frontend_project_directions"]
        ) == 3

def test_project_intelligence_response_includes_evidence_coverage():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="retrieval augmented generation for question answering",
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["ML Engineer"],
                "preferred_stack": ["Python", "FastAPI"],
            },
        )
    )

    payload = response.model_dump()

    assert payload["status"] == "ready"
    assert payload["evidence_coverage"] is not None
    assert payload["evidence_coverage"]["coverage_state"] in {
        "strong_direct",
        "adequate_direct",
        "adjacent_only",
        "exploratory",
        "cross_domain",
        "out_of_domain",
        "query_too_broad",
    }
    assert "label" in payload["evidence_coverage"]
    assert "user_message" in payload["evidence_coverage"]
    assert "can_generate_directions" in payload["evidence_coverage"]
    assert payload["evidence_coverage"]["unique_source_count"] > 0

def test_explicit_user_domain_is_preserved_over_weaker_inferred_focus():
    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="AR VR education project",
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Software Engineer"],
                "preferred_stack": ["Python", "FastAPI", "React"],
            },
        )
    )

    payload = response.model_dump()

    assert payload["status"] == "ready"
    assert payload["detected_domain"] == "education_tech"
    assert payload["resolved_planning_domain"] == "education_tech"
    assert payload["inferred_focus"] is not None
    assert payload["evidence_coverage"] is not None
    assert payload["evidence_coverage"]["coverage_state"] in {
        "strong_direct",
        "adequate_direct",
        "adjacent_only",
        "exploratory",
    }

def test_explicit_devops_domain_does_not_require_github_corpus(
    monkeypatch,
):
    import github_corpus_search

    monkeypatch.setattr(
        github_corpus_search,
        "GITHUB_CORPUS_PATH",
        "data/nonexistent_github_project_corpus.csv",
    )

    response = generate_project_intelligence(
        ProjectIntelligenceRequest(
            goal="DevOps observability dashboard project",
            constraints={
                "skill_level": "intermediate",
                "time_available": "3 weeks",
                "target_roles": ["Software Engineer"],
                "preferred_stack": ["Python", "FastAPI", "React"],
            },
        )
    )

    payload = response.model_dump()

    assert payload["status"] == "ready"
    assert payload["detected_domain"] == "devops"
    assert payload["resolved_planning_domain"] == "devops"

