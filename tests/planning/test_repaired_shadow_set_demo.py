import json
from pathlib import Path

import pytest

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
)
from planning.repaired_shadow_set import RepairedShadowSetEvaluation
from planning.repaired_shadow_set_demo import (
    build_repaired_shadow_set_artifact,
    load_accepted_replacement,
    write_repaired_shadow_set_artifact,
)
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)


def make_source():
    return RegenerationSourceArtifact(
        path=Path("source.json"),
        brief=EvidenceBrief(
            query="Build a data engineering project.",
            sources=[
                EvidenceSource(
                    source_id="paper-1",
                    source_type="research_paper",
                    title="Data Quality Research",
                    excerpt="Reliability needs observability.",
                    support_scope="direct",
                )
            ],
        ),
        request=CandidateGenerationRequest(
            user_goal="Build a data engineering project."
        ),
        directive=DiversificationRepairDirective(
            replace_candidate_title="Failure Triage",
            retain_candidate_titles=["Pipeline Monitor"],
            highest_pair_similarity=0.79,
            reason="Close semantic pair.",
        ),
        retained_candidates=[],
        surviving_candidates=[],
        replaced_candidate=CandidateDirection(
            title="Failure Triage",
            problem_statement="Teams need triage.",
            target_user="Data engineers",
            core_workflow=["Group failures.", "Prioritize incidents."],
            mvp_scope=[
                "Load failures.",
                "Group patterns.",
                "Show priorities.",
            ],
            success_metrics=["Faster review."],
            evidence_relationship="Uses retained evidence.",
            source_ids=["paper-1"],
        ),
    )


def accepted_artifact():
    return {
        "cycle": {
            "intake": {
                "candidate": {
                    "title": "Lineage Blast Radius Explorer",
                    "problem_statement": (
                        "Teams need downstream impact visibility."
                    ),
                    "target_user": "Data engineers",
                    "core_workflow": [
                        "Load known incidents.",
                        "Trace downstream dependencies.",
                    ],
                    "mvp_scope": [
                        "Store lineage edges.",
                        "Compute blast radius.",
                        "Show impact report.",
                    ],
                    "success_metrics": ["Faster impact review."],
                    "evidence_relationship": "Uses retained evidence.",
                    "source_ids": ["paper-1"],
                    "assumptions": [],
                    "suggested_stack": ["Python", "FastAPI"],
                }
            },
            "replacement_evaluation": {
                "accepted_as_diverse_replacement": True
            },
        }
    }


def test_loads_accepted_replacement_from_saved_artifact(tmp_path):
    path = tmp_path / "accepted.json"
    path.write_text(json.dumps(accepted_artifact()))

    candidate = load_accepted_replacement(
        regeneration_path=path,
        source=make_source(),
    )

    assert candidate.title == "Lineage Blast Radius Explorer"


def test_rejects_saved_regeneration_that_was_not_accepted(tmp_path):
    payload = accepted_artifact()
    payload["cycle"]["replacement_evaluation"][
        "accepted_as_diverse_replacement"
    ] = False

    path = tmp_path / "rejected.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="not accepted"):
        load_accepted_replacement(
            regeneration_path=path,
            source=make_source(),
        )


def test_writes_repaired_shadow_set_artifact(tmp_path):
    result = RepairedShadowSetEvaluation(
        status="repaired_ready",
        replaced_candidate_title="Failure Triage",
        replacement_candidate_title="Lineage Blast Radius Explorer",
        ranked_candidates=[],
        selected_candidates=[],
        semantic_candidate_diversity={"passed": True},
        grounding_adequacy=[],
        quality_warnings={},
        promotion_eligibility=[],
        signals={
            "eligible_candidate_count": 3,
            "semantic_diversity_passed": True,
        },
    )

    artifact = build_repaired_shadow_set_artifact(
        source_path=Path("source.json"),
        regeneration_path=Path("accepted.json"),
        directive_index=0,
        result=result,
    )

    output_path = write_repaired_shadow_set_artifact(
        artifact=artifact,
        output_dir=tmp_path,
    )

    saved = json.loads(output_path.read_text())

    assert saved["execution_mode"] == "local_repaired_shadow_set"
    assert saved["repaired_shadow_set"]["status"] == "repaired_ready"
