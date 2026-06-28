from planning.candidate_models import CandidateDirection
from planning.candidate_validator import (
    validate_candidate,
    validate_candidate_set,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def make_brief():
    return EvidenceBrief(
        query="Build an investigation platform.",
        sources=[
            EvidenceSource(
                source_id="paper-1",
                source_type="research_paper",
                title="Event Correlation",
                excerpt="Event correlation for investigation workflows.",
            )
        ],
    )


def make_candidate(**overrides):
    candidate = CandidateDirection(
        title="Incident Correlation Workbench",
        problem_statement="Incident evidence is fragmented.",
        target_user="Platform engineers",
        core_workflow=[
            "Ingest incident signals.",
            "Correlate events into an investigation timeline.",
        ],
        mvp_scope=[
            "Load sample incident records.",
            "Correlate related events.",
            "Show an investigation timeline.",
        ],
        success_metrics=[
            "Time to identify related events.",
        ],
        evidence_relationship=(
            "Uses the evidence brief as support for event-correlation workflows."
        ),
        source_ids=["paper-1"],
    )

    for key, value in overrides.items():
        setattr(candidate, key, value)

    return candidate


def test_valid_candidate_passes():
    result = validate_candidate(
        make_candidate(),
        make_brief(),
    )

    assert result.is_valid is True
    assert result.errors == []


def test_unknown_source_id_is_rejected():
    result = validate_candidate(
        make_candidate(source_ids=["made-up-source"]),
        make_brief(),
    )

    assert result.is_valid is False
    assert "outside the evidence brief" in result.errors[0]


def test_candidate_without_named_source_gets_honesty_warning():
    result = validate_candidate(
        make_candidate(source_ids=[]),
        make_brief(),
    )

    assert result.is_valid is True
    assert "planning-domain support" in result.warnings[0]


def test_duplicate_titles_are_rejected():
    results = validate_candidate_set(
        [
            make_candidate(),
            make_candidate(),
        ],
        make_brief(),
    )

    assert results[1].is_valid is False
    assert "duplicates another direction" in results[1].errors[0]
