from pathlib import Path

from planning.candidate_models import (
    CandidateDirection,
    CandidateGenerationRequest,
)
from planning.evidence_support import CandidateEvidenceSupportScorer
from planning.planner_models import EvidenceBrief, EvidenceSource
from planning.regeneration_source_artifact import (
    RegenerationSourceArtifact,
)
from planning.repaired_shadow_set import (
    evaluate_repaired_shadow_set,
)
from planning.semantic_candidate_diversity import (
    SemanticCandidateDiversityScorer,
)
from planning.semantic_diversification_repair import (
    DiversificationRepairDirective,
)
from planning.semantic_goal_relevance import EmbeddingVector


class ControlledEncoder:
    def encode_text(self, text):
        if "Pipeline Monitor" in text:
            return EmbeddingVector((1.0, 0.0))

        if "Schema Drift Guard" in text:
            return EmbeddingVector((0.0, 1.0))

        if "Lineage Blast Radius Explorer" in text:
            return EmbeddingVector((0.7, 0.7))

        if "Data Quality Research" in text:
            return EmbeddingVector((0.7, 0.7))

        raise AssertionError(f"Unexpected text: {text}")


def candidate(title, workflow, scope):
    return CandidateDirection(
        title=title,
        problem_statement="Data teams need an inspectable workflow.",
        target_user="Data engineers",
        core_workflow=workflow,
        mvp_scope=scope,
        success_metrics=["Issues become easier to prioritize."],
        evidence_relationship="Uses retained data-quality evidence.",
        source_ids=["paper-1"],
        suggested_stack=["Python", "FastAPI"],
    )


def make_source():
    monitor = candidate(
        "Pipeline Monitor",
        ["Run validation checks.", "Show quality alerts."],
        [
            "Load records.",
            "Run validation checks.",
            "Show alert results.",
        ],
    )
    schema_guard = candidate(
        "Schema Drift Guard",
        [
            "Compare schemas with contracts.",
            "Explain changed fields.",
        ],
        [
            "Load schema snapshots.",
            "Compare contract versions.",
            "Show drift findings.",
        ],
    )

    return RegenerationSourceArtifact(
        path=Path("source.json"),
        brief=EvidenceBrief(
            query="Build a data pipeline quality project.",
            sources=[
                EvidenceSource(
                    source_id="paper-1",
                    source_type="research_paper",
                    title="Data Quality Research",
                    excerpt="Data reliability needs observability.",
                    support_scope="direct",
                )
            ],
        ),
        request=CandidateGenerationRequest(
            user_goal="Build a data pipeline quality project.",
            skill_level="intermediate",
            time_available="3 weeks",
            target_roles=["Data Engineer"],
            preferred_stack=["Python", "FastAPI"],
        ),
        directive=DiversificationRepairDirective(
            replace_candidate_title="Failure Triage",
            retain_candidate_titles=["Pipeline Monitor"],
            highest_pair_similarity=0.7915,
            reason="Close semantic pair.",
        ),
        retained_candidates=[monitor],
        surviving_candidates=[monitor, schema_guard],
        replaced_candidate=candidate(
            "Failure Triage",
            ["Group failures.", "Prioritize incidents."],
            [
                "Load failure data.",
                "Group failure patterns.",
                "Show priorities.",
            ],
        ),
    )


def test_rebuilds_distinct_repaired_three_candidate_set():
    replacement = candidate(
        "Lineage Blast Radius Explorer",
        [
            "Ingest known incidents and lineage edges.",
            "Trace affected downstream assets.",
        ],
        [
            "Store incidents and lineage edges.",
            "Compute blast-radius scores.",
            "Show downstream impact reports.",
        ],
    )
    encoder = ControlledEncoder()

    result = evaluate_repaired_shadow_set(
        source=make_source(),
        replacement=replacement,
        evidence_support_scorer=CandidateEvidenceSupportScorer(
            encoder
        ),
        semantic_diversity_scorer=SemanticCandidateDiversityScorer(
            encoder
        ),
    )

    assert result.status == "repaired_ready"
    assert result.signals["input_candidate_count"] == 3
    assert result.signals["selected_candidate_count"] == 3
    assert result.signals["semantic_diversity_passed"] is True
    assert result.signals["eligible_candidate_count"] == 3
    assert result.replacement_candidate_title == (
        "Lineage Blast Radius Explorer"
    )
