import pytest

from query_semantics import (
    build_query_semantic_snapshot,
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
            None,
            None,
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
        (
            "want a data scientist dashboard for my job",
            None,
            None,
            True,
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


def test_same_segment_domain_conflict_abstains():
    snapshot = build_query_semantic_snapshot(
        "want a data scientist dashboard for my job"
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
