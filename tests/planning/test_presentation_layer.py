from planning.evidence_cards import EvidenceCard
from planning.presentation_layer import (
    build_presentation_project_directions,
    to_presentation_project_direction,
)


def _card(source_id="source-1", source_type="research_paper"):
    return EvidenceCard(
        source_id=source_id,
        source_type=source_type,
        title="Grounded Source",
        support_scope="direct",
        evidence_confidence="Strong",
        key_excerpt="Grounded evidence.",
        specific_method_or_technique=None,
        specific_dataset_or_benchmark=None,
        specific_implementation_signal=None,
        grounding_warning=None,
        relevance_signal="plausible",
        relevance_statuses=("lexically_supported",),
        linked_candidate_titles=(),
        user_facing_explanation="Grounded source.",
    )


def _direction(confidence="Strong"):
    return {
        "scope_level": "medium",
        "build_type": "resume_mvp",
        "estimated_time": "3-5 days",
        "title": "Grounded RAG Evaluation Dashboard",
        "problem_statement": "Build a RAG evaluation dashboard.",
        "why_this_is_grounded": (
            "This project is grounded in RAG evaluation evidence."
        ),
        "source_ids": ["source-1"],
        "evidence_confidence": confidence,
        "grounding_warnings": [],
        "mvp_scope": [
            "a retrieval pipeline",
            "an answer evaluation view",
            "a citation checker",
        ],
        "skills_demonstrated": [
            "RAG evaluation",
            "FastAPI",
            "FAISS retrieval",
            "Evidence validation",
        ],
        "interview_talking_points": [
            "I built a RAG evaluation dashboard grounded in research evidence."
        ],
    }


def test_presentation_direction_contains_no_internal_fields():
    result = to_presentation_project_direction(
        direction=_direction(),
        evidence_cards=[_card()],
    ).to_dict()

    internal_fields = [
        "source_ids",
        "invented_source_ids",
        "grounding_adequacy",
        "token_estimate",
        "routing_preview",
        "safety_pipeline",
        "validation_traces",
        "evidence_cards",
    ]

    for field in internal_fields:
        assert field not in result


def test_exploratory_confidence_produces_open_questions():
    result = to_presentation_project_direction(
        direction=_direction(confidence="Exploratory"),
        evidence_cards=[_card()],
    )

    assert result.open_questions
    assert (
        "Exploratory" in result.evidence_badge
        or "open research" in result.evidence_badge.lower()
    )


def test_strong_evidence_produces_badge_and_explanation():
    result = to_presentation_project_direction(
        direction=_direction(confidence="Strong"),
        evidence_cards=[_card(), _card("source-2", "github_repository")],
    )

    assert result.evidence_badge
    assert "support" in result.evidence_badge.lower()
    assert result.confidence_explanation
    assert result.evidence_summary


def test_invalid_preview_hides_presentation_directions():
    class Validation:
        is_valid = False

    result = build_presentation_project_directions(
        parsed_response={"project_directions": [_direction()]},
        evidence_cards=[_card()],
        preview_validation=Validation(),
    )

    assert result == []


def test_presentation_title_removes_internal_fallback_prefixes():
    result = to_presentation_project_direction(
        direction={
            **_direction(),
            "title": "Quick Evidence Trace: RAG Evaluation Dashboard",
        },
        evidence_cards=[_card()],
    )

    assert result.title == "RAG Evaluation Dashboard Starter"


def test_presentation_skills_hide_backend_internal_phrasing():
    result = to_presentation_project_direction(
        direction={
            **_direction(),
            "skills_demonstrated": [
                "evidence-grounded planning",
                "validation-driven LLM safety",
                "deterministic fallback design",
            ],
        },
        evidence_cards=[_card()],
    )

    assert result.skills_shown == [
        "Product-minded ML planning",
        "Evaluation and validation",
        "Reliable system design",
    ]


def test_presentation_talking_point_hides_invalid_llm_output_phrasing():
    result = to_presentation_project_direction(
        direction={
            **_direction(),
            "interview_talking_points": [
                "Explain why invalid LLM output should not be shown directly."
            ],
        },
        evidence_cards=[_card()],
    )

    assert result.interview_talking_point == (
        "I built a project that turns evidence into actionable "
        "recommendations while validating the quality of the output."
    )


def test_what_you_will_build_uses_clean_title_and_mvp_scope():
    result = to_presentation_project_direction(
        direction={
            **_direction(),
            "title": "Evidence-Grounded MVP: RAG Evaluation Dashboard",
            "mvp_scope": [
                "a retrieval pipeline",
                "an evaluation dashboard",
                "a grounding checker",
            ],
        },
        evidence_cards=[_card()],
    )

    assert result.what_you_will_build == (
        "You will build rag evaluation dashboard mvp: "
        "a retrieval pipeline; an evaluation dashboard; "
        "a grounding checker."
    )


def test_why_it_matters_explains_grounding_without_raw_internal_language():
    result = to_presentation_project_direction(
        direction={
            **_direction(),
            "why_this_is_grounded": (
                "it is supported by research and implementation evidence."
            ),
        },
        evidence_cards=[_card()],
    )

    assert result.why_it_matters == (
        "This is stronger than a generic tutorial project because "
        "it is supported by research and implementation evidence."
    )
    assert "source_ids" not in result.why_it_matters
    assert "token" not in result.why_it_matters.lower()
