from planning.candidate_regeneration_intake import (
    intake_regenerated_candidate,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def make_brief():
    return EvidenceBrief(
        query="Build a data pipeline quality project.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Data Quality Monitoring Research",
                excerpt="Validation improves pipeline reliability.",
                support_scope="direct",
            )
        ],
    )


def valid_response(source_ids=None):
    return {
        "candidate": {
            "title": "Schema Drift Contract Guard",
            "problem_statement": (
                "Data engineers need earlier visibility into schema drift."
            ),
            "target_user": "Data engineers",
            "core_workflow": [
                "Compare incoming schemas with expected contracts.",
                "Surface drift events and affected fields.",
            ],
            "mvp_scope": [
                "Load representative schema snapshots.",
                "Compare schemas against a versioned contract.",
                "Show drift findings in a review view.",
            ],
            "success_metrics": [
                "Number of schema-drift issues detected.",
            ],
            "evidence_relationship": (
                "Uses retained data-quality evidence for validation design."
            ),
            "source_ids": source_ids or ["paper-1"],
            "assumptions": [
                "The MVP uses versioned sample schemas.",
            ],
            "suggested_stack": ["Python", "FastAPI"],
        }
    }


def test_intake_parses_and_validates_regenerated_candidate():
    intake = intake_regenerated_candidate(
        payload=valid_response(),
        brief=make_brief(),
    )

    assert intake.is_valid is True
    assert intake.candidate.title == "Schema Drift Contract Guard"
    assert intake.validation.errors == []


def test_intake_keeps_invalid_source_ids_visible_to_validation():
    intake = intake_regenerated_candidate(
        payload=valid_response(source_ids=["invented-source"]),
        brief=make_brief(),
    )

    assert intake.is_valid is False
    assert "outside the evidence brief" in intake.validation.errors[0]
