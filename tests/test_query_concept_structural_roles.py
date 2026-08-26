import pytest

import query_concept_resolution as qcr


# =========================================================
# L2.7A STRUCTURAL ROLE GOLD REGRESSION
#
# These cases were manually adjudicated independently and
# validated against the production occurrence-aware role path.
#
# Retrieval evidence is deliberately disabled in these tests:
# grammatical role must depend on query structure and occurrence
# provenance, not corpus contents or taxonomy coverage.
# =========================================================


GOLD_CASES = [
    (
        "python used before now want python backend project",
        "python",
        (28, 34),
        "goal",
    ),
    (
        "need project for job maybe ml engineer",
        "ml",
        (27, 29),
        "role",
    ),
    (
        "aws know already want aws cloud project",
        "cloud",
        (26, 31),
        "goal",
    ),
    (
        "python used before now want python backend project",
        "backend",
        (35, 42),
        "goal",
    ),
    (
        "want improve kubernetes skills",
        "kubernetes",
        (13, 23),
        "skill_target",
    ),
    (
        "i know react just want something ml for resume",
        "ml",
        (33, 35),
        "goal",
    ),
    (
        "want become ml engineer",
        "engineer",
        (15, 23),
        "role",
    ),
    (
        "umm want cloud project maybe aws idk",
        "cloud",
        (9, 14),
        "goal",
    ),
    (
        "using qwen milvus gradio want retrieval project",
        "retrieval",
        (30, 39),
        "goal",
    ),
    (
        "I want something for a data engineer role.",
        "data",
        (23, 27),
        "role",
    ),
    (
        "rag basics know want rag evaluator",
        "rag",
        (21, 24),
        "goal",
    ),
    (
        "need project for job maybe ml engineer",
        "ml engineer",
        (27, 38),
        "role",
    ),
    (
        "I want to use FastAPI for the backend.",
        "fastapi",
        (14, 21),
        "stack_preference",
    ),
    (
        "react i used before now ml project want",
        "ml",
        (24, 26),
        "unknown",
    ),
    (
        "i python know but kubernetes want learn",
        "kubernetes",
        (18, 28),
        "unknown",
    ),
    (
        "aws know already want aws cloud project",
        "aws",
        (22, 25),
        "goal",
    ),
    (
        "want become ml engineer",
        "ml engineer",
        (12, 23),
        "role",
    ),
    (
        "need project for job maybe ml engineer",
        "engineer",
        (30, 38),
        "role",
    ),
    (
        "want become ml engineer",
        "ml",
        (12, 14),
        "role",
    ),
    (
        "cybersecurity analyst portfolio",
        "cybersecurity analyst",
        (0, 21),
        "role",
    ),
    (
        "I want something for a data engineer role.",
        "data engineer",
        (23, 36),
        "role",
    ),
    (
        "cybersecurity analyst portfolio",
        "analyst",
        (14, 21),
        "role",
    ),
    (
        "targeting data engineering roles",
        "engineering",
        (15, 26),
        "role",
    ),
    (
        "cybersecurity analyst portfolio",
        "cybersecurity",
        (0, 13),
        "role",
    ),
    (
        "I know Python already, but I want to use Python "
        "for a data engineering project.",
        "python",
        (41, 47),
        "stack_preference",
    ),
    (
        "I want a project that uses Python and helps me "
        "learn Kubernetes.",
        "kubernetes",
        (53, 63),
        "skill_target",
    ),
    (
        "targeting data engineering roles",
        "data engineering",
        (10, 26),
        "role",
    ),
    (
        "want learn kubernetes",
        "kubernetes",
        (11, 21),
        "skill_target",
    ),
    (
        "target cloud engineer roles",
        "cloud engineer",
        (7, 21),
        "role",
    ),
    (
        "rag basics know want rag evaluator",
        "rag evaluator",
        (21, 34),
        "goal",
    ),
    (
        "targeting data engineering roles",
        "data",
        (10, 14),
        "role",
    ),
    (
        "want practice kubernetes",
        "kubernetes",
        (14, 24),
        "skill_target",
    ),
    (
        "python project where i learn docker",
        "docker",
        (29, 35),
        "skill_target",
    ),
    (
        "target cloud engineer roles",
        "engineer",
        (13, 21),
        "role",
    ),
    (
        "rag basics know want rag evaluator",
        "evaluator",
        (25, 34),
        "goal",
    ),
    (
        "I want a project that uses Python and helps me "
        "learn Kubernetes.",
        "python",
        (27, 33),
        "stack_preference",
    ),
    (
        "basically python react but need ai project",
        "ai",
        (32, 34),
        "goal",
    ),
    (
        "I want something for a data engineer role.",
        "engineer",
        (28, 36),
        "role",
    ),
    (
        "target cloud engineer roles",
        "cloud",
        (7, 12),
        "role",
    ),
    (
        "bro i know react just want something ml for resume",
        "ml",
        (37, 39),
        "goal",
    ),
]


def _find_generated_occurrence(
    query,
    normalized,
    char_span,
):
    matches = [
        span
        for span in qcr.generate_structured_ngram_spans(
            query,
            max_n=4,
        )
        if (
            span.normalized_form == normalized
            and span.char_span == char_span
        )
    ]

    assert len(matches) == 1, (
        query,
        normalized,
        char_span,
        [
            (
                span.normalized_form,
                span.char_span,
                span.segment_index,
            )
            for span in qcr.generate_structured_ngram_spans(
                query,
                max_n=4,
            )
        ],
    )

    return matches[0]


def _production_role_rows(query):
    """
    Return occurrence-aware role assignments through the actual
    promoted production role entry point.

    Retrieval evidence is intentionally bypassed here because
    these tests validate grammatical role assignment only.
    """
    rows = []

    for span in qcr.generate_structured_ngram_spans(
        query,
        max_n=4,
    ):
        role = qcr._best_clause_role_for_span(
            span.surface_form,
            query,
            char_span=span.char_span,
            segment_index=span.segment_index,
        )

        rows.append(
            {
                "surface": span.surface_form,
                "normalized": span.normalized_form,
                "char_span": span.char_span,
                "segment_index": span.segment_index,
                "role": role.value,
            }
        )

    return rows


@pytest.mark.parametrize(
    (
        "query",
        "normalized",
        "char_span",
        "expected_role",
    ),
    GOLD_CASES,
)
def test_structural_role_gold_cases(
    monkeypatch,
    query,
    normalized,
    char_span,
    expected_role,
):
    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: [],
    )

    span = _find_generated_occurrence(
        query,
        normalized,
        char_span,
    )

    resolved = qcr.resolve_concept_span(
        span.surface_form,
        query=query,
        char_span=span.char_span,
        constituent_char_spans=(
            span.constituent_char_spans
        ),
        segment_index=span.segment_index,
    )

    assert (
        resolved.clause_role.value
        == expected_role
    )


@pytest.mark.parametrize(
    (
        "query",
        "normalized",
        "expected_role",
    ),
    [
        (
            "teach me aws",
            "aws",
            "skill_target",
        ),
        (
            "project teach me aws",
            "aws",
            "skill_target",
        ),
        (
            "project teaches me aws",
            "aws",
            "skill_target",
        ),
        (
            "build a project that teaches me aws",
            "aws",
            "skill_target",
        ),
    ],
)
def test_teach_cue_forms(
    monkeypatch,
    query,
    normalized,
    expected_role,
):
    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: [],
    )

    candidates = [
        span
        for span in qcr.generate_structured_ngram_spans(
            query,
            max_n=4,
        )
        if span.normalized_form == normalized
    ]

    assert len(candidates) == 1

    span = candidates[0]

    result = qcr.resolve_concept_span(
        span.surface_form,
        query=query,
        char_span=span.char_span,
        constituent_char_spans=(
            span.constituent_char_spans
        ),
        segment_index=span.segment_index,
    )

    assert (
        result.clause_role.value
        == expected_role
    )


def test_open_world_identity_does_not_control_role(
    monkeypatch,
):
    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: [],
    )

    cases = [
        (
            "build something with ZorvexQL",
            "zorvexql",
            "stack_preference",
        ),
        (
            "build something with QuuxDB77",
            "quuxdb77",
            "stack_preference",
        ),
        (
            "i know BlorbX but want FlimNet99",
            "blorbx",
            "skill_held",
        ),
        (
            "i know BlorbX but want FlimNet99",
            "flimnet99",
            "goal",
        ),
    ]

    for query, normalized, expected in cases:
        candidates = [
            span
            for span
            in qcr.generate_structured_ngram_spans(
                query,
                max_n=4,
            )
            if span.normalized_form == normalized
        ]

        assert len(candidates) == 1

        span = candidates[0]

        result = qcr.resolve_concept_span(
            span.surface_form,
            query=query,
            char_span=span.char_span,
            constituent_char_spans=(
                span.constituent_char_spans
            ),
            segment_index=span.segment_index,
        )

        assert result.clause_role.value == expected


def test_keyword_only_input_does_not_invent_roles(
    monkeypatch,
):
    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: [],
    )

    query = "python react ai"

    spans = qcr.generate_structured_ngram_spans(
        query,
        max_n=4,
    )

    assert spans

    for span in spans:
        result = qcr.resolve_concept_span(
            span.surface_form,
            query=query,
            char_span=span.char_span,
            constituent_char_spans=(
                span.constituent_char_spans
            ),
            segment_index=span.segment_index,
        )

        assert (
            result.clause_role
            == qcr.ClauseRole.UNKNOWN
        )


def test_bounded_role_does_not_cross_relative_clause():
    query = (
        "I want a project for React that helps "
        "with data roles."
    )

    rows = _production_role_rows(query)

    react = [
        row
        for row in rows
        if row["normalized"] == "react"
    ]

    assert react
    assert all(
        row["role"] == "goal"
        for row in react
    )


def test_goal_and_later_role_target_remain_separate():
    query = (
        "I want to build an AI project "
        "for an ML engineer role."
    )

    rows = _production_role_rows(query)

    roles = {
        row["normalized"]: row["role"]
        for row in rows
    }

    assert roles["ai"] == "goal"
    assert roles["ml"] == "role"
    assert roles["engineer"] == "role"
    assert roles["ml engineer"] == "role"


def test_long_bounded_role_title_is_not_limited_by_token_count():
    query = (
        "I want something for a senior "
        "machine learning platform engineer role."
    )

    rows = _production_role_rows(query)

    roles = {
        row["normalized"]: row["role"]
        for row in rows
    }

    assert (
        roles[
            "senior machine learning platform"
        ]
        == "role"
    )

    assert (
        roles[
            "machine learning platform engineer"
        ]
        == "role"
    )


def test_role_morphology_does_not_leak_into_dashboard_goal():
    query = (
        "want a data scientist dashboard for my job"
    )

    rows = _production_role_rows(query)

    roles = {
        row["normalized"]: row["role"]
        for row in rows
    }

    assert roles["dashboard"] == "goal"

    # The larger project concepts must not inherit ROLE merely
    # because an earlier occupational head exists in the segment.
    assert (
        roles["scientist dashboard"]
        == "goal"
    )

    assert (
        roles["data scientist dashboard"]
        == "goal"
    )


def test_role_morphology_does_not_leak_into_interview_prep_goal():
    query = (
        "want data engineer interview prep "
        "for my portfolio"
    )

    rows = _production_role_rows(query)

    roles = {
        row["normalized"]: row["role"]
        for row in rows
    }

    assert roles["interview"] == "goal"
    assert roles["prep"] == "goal"
    assert roles["interview prep"] == "goal"
