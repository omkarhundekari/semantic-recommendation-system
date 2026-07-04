from planning.candidate_models import CandidateDirection
from planning.evidence_support import (
    CandidateEvidenceSupportAssessment,
    CitedSourceAlignment,
)
from planning.grounding_adequacy import (
    GroundingAdequacy,
    assess_grounding_adequacy,
)
from planning.planner_models import EvidenceBrief, EvidenceSource


def make_candidate(source_ids):
    return CandidateDirection(
        title="Incident Timeline Correlator",
        problem_statement="Correlate deployment and service-health signals.",
        target_user="Platform engineers",
        core_workflow=[
            "Ingest deployment events.",
            "Correlate signals into an incident timeline.",
        ],
        mvp_scope=[
            "Load sample events.",
            "Correlate related signals.",
            "Show an investigation timeline.",
        ],
        success_metrics=["Time to identify related events."],
        evidence_relationship="Uses evidence for incident correlation.",
        source_ids=source_ids,
    )


def make_brief():
    return EvidenceBrief(
        query="Build an incident investigation tool.",
        sources=[
            EvidenceSource(
                source_id="paper-direct",
                source_type="research_paper",
                title="Event Correlation for Incidents",
                excerpt="Correlate operational events during incidents.",
                support_scope="direct",
            ),
            EvidenceSource(
                source_id="repo-adjacent",
                source_type="github_repository",
                title="Observability Pipeline",
                excerpt="Normalize service observability data.",
                support_scope="adjacent_planning",
            ),
        ],
    )


def make_assessment(
    *,
    provided_count,
    valid_count,
    direct_count,
    adjacent_count,
    alignments,
):
    return CandidateEvidenceSupportAssessment(
        candidate_title="Incident Timeline Correlator",
        citation_integrity={
            "provided_count": provided_count,
            "valid_count": valid_count,
            "invalid_count": provided_count - valid_count,
            "valid_fraction": (
                round(valid_count / provided_count, 4)
                if provided_count
                else 0.0
            ),
        },
        direct_citation_count=direct_count,
        adjacent_citation_count=adjacent_count,
        uncited_candidate=(provided_count == 0),
        cited_source_alignments=alignments,
    )


def test_uncited_candidate_with_direct_sources_is_uncited_covered():
    trace = assess_grounding_adequacy(
        candidate=make_candidate([]),
        brief=make_brief(),
        assessment=make_assessment(
            provided_count=0,
            valid_count=0,
            direct_count=0,
            adjacent_count=0,
            alignments=[],
        ),
    )

    assert trace.adequacy_class == GroundingAdequacy.UNCITED_COVERED
    assert trace.direct_sources_in_brief == 1
    assert trace.uncited_direct_sources == ["paper-direct"]
    assert trace.cited_alignment_scores == []


def test_candidate_with_direct_scope_citation_is_classified_without_threshold():
    trace = assess_grounding_adequacy(
        candidate=make_candidate(["paper-direct"]),
        brief=make_brief(),
        assessment=make_assessment(
            provided_count=1,
            valid_count=1,
            direct_count=1,
            adjacent_count=0,
            alignments=[
                CitedSourceAlignment(
                    source_id="paper-direct",
                    source_type="research_paper",
                    support_scope="direct",
                    raw_cosine=0.12,
                    normalized_score=0.56,
                )
            ],
        ),
    )

    assert trace.adequacy_class == GroundingAdequacy.CITED_WITH_DIRECT_SCOPE
    assert trace.min_cited_alignment == 0.12
    assert trace.max_cited_alignment == 0.12


def test_candidate_with_only_adjacent_sources_is_classified_separately():
    trace = assess_grounding_adequacy(
        candidate=make_candidate(["repo-adjacent"]),
        brief=make_brief(),
        assessment=make_assessment(
            provided_count=1,
            valid_count=1,
            direct_count=0,
            adjacent_count=1,
            alignments=[
                CitedSourceAlignment(
                    source_id="repo-adjacent",
                    source_type="github_repository",
                    support_scope="adjacent_planning",
                    raw_cosine=0.48,
                    normalized_score=0.74,
                )
            ],
        ),
    )

    assert trace.adequacy_class == GroundingAdequacy.CITED_ONLY_ADJACENT
    assert trace.uncited_direct_sources == ["paper-direct"]


def test_uncited_candidate_without_direct_sources_is_uncited_sparse():
    brief = EvidenceBrief(
        query="Build an incident investigation tool.",
        sources=[
            EvidenceSource(
                source_id="repo-adjacent",
                source_type="github_repository",
                title="Observability Pipeline",
                excerpt="Normalize service observability data.",
                support_scope="adjacent_planning",
            )
        ],
    )

    trace = assess_grounding_adequacy(
        candidate=make_candidate([]),
        brief=brief,
        assessment=make_assessment(
            provided_count=0,
            valid_count=0,
            direct_count=0,
            adjacent_count=0,
            alignments=[],
        ),
    )

    assert trace.adequacy_class == GroundingAdequacy.UNCITED_SPARSE
    assert trace.direct_sources_in_brief == 0
    assert trace.uncited_direct_sources == []


def test_invalid_citations_are_not_misclassified_as_uncited():
    trace = assess_grounding_adequacy(
        candidate=make_candidate(["missing-paper"]),
        brief=make_brief(),
        assessment=make_assessment(
            provided_count=1,
            valid_count=0,
            direct_count=0,
            adjacent_count=0,
            alignments=[],
        ),
    )

    assert trace.adequacy_class == GroundingAdequacy.INVALID_CITATIONS
