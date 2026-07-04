from planning.candidate_models import CandidateDirection
from planning.planner_models import EvidenceBrief, EvidenceSource


class ControlledEncoder:
    def encode_text(self, text):
        from planning.semantic_goal_relevance import EmbeddingVector

        if "Incident Timeline Correlator" in text:
            return EmbeddingVector(values=(1.0, 0.0))

        if "Event Correlation for Cloud Incidents" in text:
            return EmbeddingVector(values=(0.9, 0.1))

        if "Continuous Health Event Retrieval" in text:
            return EmbeddingVector(values=(0.0, 1.0))

        if "Observability Data Pipeline" in text:
            return EmbeddingVector(values=(0.7, 0.7))

        raise AssertionError(f"Unexpected text: {text}")


def make_candidate(source_ids):
    return CandidateDirection(
        title="Incident Timeline Correlator",
        problem_statement=(
            "Correlate deployment changes, service health signals, "
            "and operational events during incidents."
        ),
        target_user="Platform engineers investigating incidents",
        core_workflow=[
            "Ingest deployment and service-health events.",
            "Correlate related signals into an incident timeline.",
        ],
        mvp_scope=[
            "Load sample deployment events.",
            "Correlate timeline signals.",
            "Show likely incident relationships.",
        ],
        success_metrics=["Time to identify related incident events."],
        evidence_relationship="Uses cited evidence for incident correlation.",
        source_ids=source_ids,
    )


def make_brief():
    return EvidenceBrief(
        query="Build a cloud incident investigation project.",
        sources=[
            EvidenceSource(
                source_id="paper-aligned",
                source_type="research_paper",
                title="Event Correlation for Cloud Incidents",
                excerpt=(
                    "Correlate deployment changes and service events "
                    "during cloud incident investigation."
                ),
                support_scope="direct",
            ),
            EvidenceSource(
                source_id="paper-misaligned",
                source_type="research_paper",
                title="Continuous Health Event Retrieval",
                excerpt=(
                    "Retrieve events from continuous personal health data."
                ),
                support_scope="direct",
            ),
            EvidenceSource(
                source_id="repo-adjacent",
                source_type="github_repository",
                title="Observability Data Pipeline",
                excerpt=(
                    "Normalize observability data from multiple services."
                ),
                support_scope="adjacent_planning",
            ),
        ],
    )


def test_evidence_support_keeps_scope_and_detects_alignment_quality():
    from planning.evidence_support import CandidateEvidenceSupportScorer

    assessment = CandidateEvidenceSupportScorer(
        encoder=ControlledEncoder()
    ).assess_candidate(
        candidate=make_candidate(
            ["paper-aligned", "paper-misaligned", "repo-adjacent"]
        ),
        brief=make_brief(),
    )

    report = assessment.to_dict()
    alignments = {
        entry["source_id"]: entry
        for entry in report["cited_source_alignments"]
    }

    assert report["citation_integrity"] == {
        "provided_count": 3,
        "valid_count": 3,
        "invalid_count": 0,
        "valid_fraction": 1.0,
    }
    assert report["direct_citation_count"] == 2
    assert report["adjacent_citation_count"] == 1
    assert report["uncited_candidate"] is False

    assert alignments["paper-aligned"]["support_scope"] == "direct"
    assert alignments["repo-adjacent"]["support_scope"] == (
        "adjacent_planning"
    )

    assert (
        alignments["paper-aligned"]["raw_cosine"]
        > alignments["paper-misaligned"]["raw_cosine"]
    )
    assert (
        alignments["repo-adjacent"]["raw_cosine"]
        > alignments["paper-misaligned"]["raw_cosine"]
    )


def test_evidence_support_reports_uncited_candidate_without_inventing_support():
    from planning.evidence_support import CandidateEvidenceSupportScorer

    assessment = CandidateEvidenceSupportScorer(
        encoder=ControlledEncoder()
    ).assess_candidate(
        candidate=make_candidate([]),
        brief=make_brief(),
    )

    report = assessment.to_dict()

    assert report["uncited_candidate"] is True
    assert report["citation_integrity"]["provided_count"] == 0
    assert report["cited_source_alignments"] == []
    assert any(
        "no named evidence sources" in warning.lower()
        for warning in report["warnings"]
    )
