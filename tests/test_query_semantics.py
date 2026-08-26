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
