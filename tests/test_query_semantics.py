import pytest

import query_semantics
from query_semantics import (
    build_query_semantic_snapshot,
)
from query_concept_resolution import (
    ResolutionStatus,
    ResolvedConceptSpan,
)
from query_concept_understanding import (
    ClauseRole,
)


@pytest.mark.parametrize(
    (
        "query",
        "expected_focus",
        "expected_family",
        "expected_ambiguous",
    ),
    [
        (
            "I know React but want an AI project using FastAPI",
            "ai_ml",
            "ai_ml",
            False,
        ),
        (
            "I want a RAG app using Qdrant "
            "and want to learn Kubernetes",
            "rag_llm",
            "ai_ml",
            False,
        ),
        (
            "targeting data engineering roles using Python",
            "data_engineering",
            "cloud_platform",
            False,
        ),
        (
            "cybersecurity analyst portfolio using FastAPI",
            "cybersecurity",
            "cybersecurity",
            False,
        ),
        (
            "I know Python already, but I want to use Python "
            "for a data engineering project.",
            "data_engineering",
            "cloud_platform",
            False,
        ),
        (
            "python react ai",
            None,
            None,
            False,
        ),
        (
            "build something with ZorvexQL",
            None,
            None,
            False,
        ),
        (
            "I want to build an AI project "
            "for an ML engineer role.",
            "ai_ml",
            "ai_ml",
            False,
        ),
    ],
)
def test_query_semantic_domain_authority(
    query,
    expected_focus,
    expected_family,
    expected_ambiguous,
):
    snapshot = build_query_semantic_snapshot(
        query
    )

    assert (
        snapshot.primary_focus
        == expected_focus
    )

    assert (
        snapshot.primary_family
        == expected_family
    )

    assert (
        snapshot.domain_ambiguous
        == expected_ambiguous
    )


@pytest.mark.parametrize(
    "query",
    [
        "want analyst project",
        "want scientist project",
        "want evaluator project",
    ],
)
def test_weak_evidence_cannot_establish_primary_domain(
    query,
):
    snapshot = build_query_semantic_snapshot(
        query
    )

    assert snapshot.primary_focus is None
    assert snapshot.primary_family is None
    assert snapshot.domain_ambiguous is False


def test_unknown_open_world_stack_is_preserved():
    snapshot = build_query_semantic_snapshot(
        "build something with ZorvexQL"
    )

    assert snapshot.primary_focus is None

    matches = [
        span
        for span in snapshot.selected_spans
        if (
            span.normalized_form
            == "zorvexql"
        )
    ]

    assert len(matches) == 1

    assert (
        matches[0].clause_role.value
        == "stack_preference"
    )


def test_goal_domain_beats_held_skill_and_stack_domain():
    snapshot = build_query_semantic_snapshot(
        "I know React but want an AI project using FastAPI"
    )

    assert snapshot.primary_focus == "ai_ml"
    assert snapshot.primary_family == "ai_ml"


def test_role_domain_can_establish_primary_focus():
    snapshot = build_query_semantic_snapshot(
        "targeting data engineering roles using Python"
    )

    assert (
        snapshot.primary_focus
        == "data_engineering"
    )

    assert (
        snapshot.primary_family
        == "cloud_platform"
    )


def test_same_segment_domain_conflict_abstains(
    monkeypatch,
):
    resolved = (
        ResolvedConceptSpan(
            surface_form="data",
            normalized_form="data",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=(
                ResolutionStatus.EVIDENCE_RESOLVED
            ),
            confidence=0.9,
            inferred_focus="data_engineering",
            inferred_family="cloud_platform",
            domain_margin=0.8,
            support_count=3,
            source_type_count=2,
            lexical_support_count=3,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=1.0,
            supporting_evidence=tuple(),
            char_span=(5, 9),
            constituent_char_spans=((5, 9),),
            segment_index=0,
        ),
        ResolvedConceptSpan(
            surface_form="dashboard",
            normalized_form="dashboard",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=(
                ResolutionStatus.EVIDENCE_RESOLVED
            ),
            confidence=0.9,
            inferred_focus="cloud",
            inferred_family="cloud_platform",
            domain_margin=0.8,
            support_count=3,
            source_type_count=2,
            lexical_support_count=3,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=1.0,
            supporting_evidence=tuple(),
            char_span=(10, 19),
            constituent_char_spans=((10, 19),),
            segment_index=0,
        ),
    )

    monkeypatch.setattr(
        query_semantics,
        "resolve_query_spans_shadow",
        lambda *args, **kwargs: list(resolved),
    )

    snapshot = build_query_semantic_snapshot(
        "want data dashboard"
    )

    assert snapshot.primary_focus is None
    assert snapshot.primary_family is None
    assert snapshot.domain_ambiguous is True


# =========================================================
# L2.8A.6 — CANONICAL SEMANTIC ANCHOR COMPRESSION
# =========================================================


def test_anchor_compression_prefers_complete_role_phrase():
    snapshot = build_query_semantic_snapshot(
        "cybersecurity analyst portfolio using FastAPI"
    )

    anchors = list(snapshot.anchors)

    assert "cybersecurity analyst" in anchors
    assert "FastAPI" in anchors

    assert "cybersecurity" not in anchors
    assert "analyst" not in anchors


def test_anchor_compression_keeps_goal_and_role_phrase_distinct():
    snapshot = build_query_semantic_snapshot(
        "I want to build an AI project "
        "for an ML engineer role."
    )

    anchors = list(snapshot.anchors)

    assert "AI" in anchors
    assert "ML engineer" in anchors

    # The complete occupational phrase represents the same ROLE
    # occurrence more faithfully than its contained ML token.
    assert "ML" not in anchors


def test_unresolved_unknown_composite_does_not_hide_atomic_concepts():
    snapshot = build_query_semantic_snapshot(
        "python react ai"
    )

    normalized = {
        anchor.lower()
        for anchor in snapshot.anchors
    }

    assert normalized == {
        "python",
        "react",
        "ai",
    }

    assert (
        "python react ai"
        not in normalized
    )


def test_open_world_unresolved_stack_survives_anchor_compression():
    snapshot = build_query_semantic_snapshot(
        "build something with ZorvexQL"
    )

    assert list(
        snapshot.anchors
    ) == [
        "ZorvexQL",
    ]


def test_distinct_semantic_roles_are_not_compressed_together():
    snapshot = build_query_semantic_snapshot(
        "I want a RAG app using Qdrant "
        "and want to learn Kubernetes"
    )

    normalized = {
        anchor.lower()
        for anchor in snapshot.anchors
    }

    assert normalized == {
        "rag",
        "qdrant",
        "kubernetes",
    }


def test_anchor_compression_does_not_mutate_selected_provenance():
    snapshot = build_query_semantic_snapshot(
        "cybersecurity analyst portfolio using FastAPI"
    )

    selected = {
        (
            span.normalized_form,
            span.char_span,
            span.clause_role.value,
        )
        for span in snapshot.selected_spans
    }

    # Compression is presentation-only. The full occurrence lattice
    # remains available to downstream semantic reasoning.
    assert (
        "cybersecurity analyst",
        (0, 21),
        "role",
    ) in selected

    assert (
        "cybersecurity",
        (0, 13),
        "role",
    ) in selected

    assert (
        "analyst",
        (14, 21),
        "role",
    ) in selected



def test_anchor_compression_preserves_supported_unknown_phrases_but_suppresses_unresolved_synthetic_composites():
    from query_semantics import (
        build_query_semantic_snapshot,
        semantic_anchor_spans,
    )

    supported = build_query_semantic_snapshot(
        "data engineering"
    )

    supported_anchors = semantic_anchor_spans(
        supported.selected_spans,
        limit=20,
    )

    assert any(
        span.surface_form == "data engineering"
        and span.clause_role.value == "unknown"
        and span.resolution_status.value
        == "evidence_resolved"
        for span in supported_anchors
    )

    synthetic = build_query_semantic_snapshot(
        "python react ai"
    )

    synthetic_anchors = semantic_anchor_spans(
        synthetic.selected_spans,
        limit=20,
    )

    assert not any(
        span.surface_form == "python react ai"
        for span in synthetic_anchors
    )

    assert {
        span.surface_form
        for span in synthetic_anchors
    } >= {
        "python",
        "react",
        "ai",
    }



def test_a7t2_family_only_span_establishes_primary_family(
    monkeypatch,
):
    import query_semantics
    from query_concept_resolution import (
        ResolutionStatus,
        ResolvedConceptSpan,
    )
    from query_concept_understanding import ClauseRole

    resolved = (
        ResolvedConceptSpan(
            surface_form="observability",
            normalized_form="observability",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.8,
            inferred_focus=None,
            inferred_family="ai_ml",
            domain_margin=0.3,
            support_count=3,
            source_type_count=2,
            lexical_support_count=3,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(0, 13),
            constituent_char_spans=((0, 13),),
            segment_index=0,
        ),
    )

    monkeypatch.setattr(
        query_semantics,
        "resolve_query_spans_shadow",
        lambda *args, **kwargs: list(resolved),
    )

    snapshot = query_semantics.build_query_semantic_snapshot(
        "observability project"
    )

    assert snapshot.primary_focus is None
    assert snapshot.primary_family == "ai_ml"
    assert snapshot.domain_ambiguous is False


def test_a7t2_family_only_conflicts_with_other_family_focus(
    monkeypatch,
):
    import query_semantics
    from query_concept_resolution import (
        ResolutionStatus,
        ResolvedConceptSpan,
    )
    from query_concept_understanding import ClauseRole

    resolved = (
        ResolvedConceptSpan(
            surface_form="observability",
            normalized_form="observability",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.9,
            inferred_focus=None,
            inferred_family="ai_ml",
            domain_margin=0.4,
            support_count=3,
            source_type_count=2,
            lexical_support_count=3,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(0, 13),
            constituent_char_spans=((0, 13),),
            segment_index=0,
        ),
        ResolvedConceptSpan(
            surface_form="dashboard",
            normalized_form="dashboard",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.8,
            inferred_focus="cloud",
            inferred_family="cloud_platform",
            domain_margin=0.3,
            support_count=3,
            source_type_count=2,
            lexical_support_count=3,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(14, 23),
            constituent_char_spans=((14, 23),),
            segment_index=0,
        ),
    )

    monkeypatch.setattr(
        query_semantics,
        "resolve_query_spans_shadow",
        lambda *args, **kwargs: list(resolved),
    )

    snapshot = query_semantics.build_query_semantic_snapshot(
        "observability dashboard project"
    )

    assert snapshot.primary_focus is None
    assert snapshot.primary_family is None
    assert snapshot.domain_ambiguous is True



def test_a7t2_weaker_domain_hypothesis_cannot_veto_resolved_domain(
    monkeypatch,
):
    import query_semantics
    from query_concept_resolution import (
        ResolutionStatus,
        ResolvedConceptSpan,
    )
    from query_concept_understanding import ClauseRole

    resolved = (
        ResolvedConceptSpan(
            surface_form="DevOps",
            normalized_form="devops",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.55,
            inferred_focus="devops",
            inferred_family="cloud_platform",
            domain_margin=0.0,
            support_count=5,
            source_type_count=2,
            lexical_support_count=5,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(0, 6),
            constituent_char_spans=((0, 6),),
            segment_index=0,
        ),
        ResolvedConceptSpan(
            surface_form="observability",
            normalized_form="observability",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.SUPPORTED_AMBIGUOUS,
            confidence=0.76,
            inferred_focus="backend",
            inferred_family="software_engineering",
            domain_margin=0.06,
            support_count=11,
            source_type_count=3,
            lexical_support_count=11,
            lexical_source_type_count=3,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(7, 20),
            constituent_char_spans=((7, 20),),
            segment_index=0,
        ),
    )

    monkeypatch.setattr(
        query_semantics,
        "resolve_query_spans_shadow",
        lambda *args, **kwargs: list(resolved),
    )

    snapshot = query_semantics.build_query_semantic_snapshot(
        "DevOps observability project"
    )

    assert snapshot.primary_focus == "devops"
    assert snapshot.primary_family == "cloud_platform"
    assert snapshot.domain_ambiguous is False


def test_a7t2_same_authority_tier_domain_conflict_still_abstains(
    monkeypatch,
):
    import query_semantics
    from query_concept_resolution import (
        ResolutionStatus,
        ResolvedConceptSpan,
    )
    from query_concept_understanding import ClauseRole

    resolved = (
        ResolvedConceptSpan(
            surface_form="data engineering",
            normalized_form="data engineering",
            clause_role=ClauseRole.GOAL,
            ngram_size=2,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.84,
            inferred_focus="data_engineering",
            inferred_family="cloud_platform",
            domain_margin=0.97,
            support_count=6,
            source_type_count=2,
            lexical_support_count=6,
            lexical_source_type_count=2,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(0, 16),
            constituent_char_spans=((0, 4), (5, 16)),
            segment_index=0,
        ),
        ResolvedConceptSpan(
            surface_form="pipeline",
            normalized_form="pipeline",
            clause_role=ClauseRole.GOAL,
            ngram_size=1,
            resolution_status=ResolutionStatus.EVIDENCE_RESOLVED,
            confidence=0.89,
            inferred_focus=None,
            inferred_family="ai_ml",
            domain_margin=0.56,
            support_count=11,
            source_type_count=3,
            lexical_support_count=11,
            lexical_source_type_count=3,
            lexical_coverage=1.0,
            top_bm25_score=None,
            supporting_evidence=tuple(),
            char_span=(17, 25),
            constituent_char_spans=((17, 25),),
            segment_index=0,
        ),
    )

    monkeypatch.setattr(
        query_semantics,
        "resolve_query_spans_shadow",
        lambda *args, **kwargs: list(resolved),
    )

    snapshot = query_semantics.build_query_semantic_snapshot(
        "data engineering pipeline project"
    )

    assert snapshot.primary_focus is None
    assert snapshot.primary_family is None
    assert snapshot.domain_ambiguous is True
