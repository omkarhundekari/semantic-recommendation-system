import ast
from pathlib import Path

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
        role = span.clause_role

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
            clause_role=span.clause_role,
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
            clause_role=span.clause_role,
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
            clause_role=span.clause_role,
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
            clause_role=span.clause_role,
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


# =========================================================
# A.7R5 — ROLE AUTHORITY ARCHITECTURE GUARDS
#
# Evidence may change concept support, confidence, status, and
# inferred domain. It must never change the grammatical role of
# the same occurrence in the user's query.
# =========================================================


def _resolved_role_map(query):
    return {
        (
            span.normalized_form,
            span.char_span,
            span.segment_index,
        ): span.clause_role
        for span in qcr.resolve_query_spans_shadow(
            query,
            max_n=4,
            top_k=6,
        )
    }


def test_resolution_role_is_independent_of_evidence_population(
    monkeypatch,
):
    evidence = [
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Evidence A",
            category="machine_learning",
            focus="recommendation_systems",
            family="ai_ml",
            score=0.95,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=8.0,
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="Evidence B",
            category="machine_learning",
            focus="recommendation_systems",
            family="ai_ml",
            score=0.90,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Evidence C",
            category="cloud",
            focus="cloud_platform",
            family="cloud_platform",
            score=0.80,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Evidence D",
            category="machine_learning",
            focus="recommendation_systems",
            family="ai_ml",
            score=0.75,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=5.0,
        ),
    ]

    populations = {
        "full": list(evidence),
        "truncated": list(evidence[:2]),
        "reversed": list(reversed(evidence)),
        "empty": [],
    }

    queries = sorted(
        {
            case[0]
            for case in GOLD_CASES
        }
        | {
            "build something with ZorvexQL",
            "i know BlorbX but want FlimNet99",
            "python react ai",
            (
                "I know React but want an AI project "
                "using FastAPI"
            ),
        }
    )

    baseline = None

    for population_name, population in populations.items():
        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            (
                lambda *args,
                population=population,
                **kwargs: list(population)
            ),
        )

        current = {
            query: _resolved_role_map(query)
            for query in queries
        }

        if baseline is None:
            baseline = current
            continue

        assert current == baseline, (
            population_name,
            {
                query: {
                    "expected": baseline[query],
                    "actual": current[query],
                }
                for query in queries
                if current[query] != baseline[query]
            },
        )


def test_resolution_module_has_single_grammatical_role_authority():
    path = Path(
        "src/query_concept_resolution.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source,
        filename=str(path),
    )

    forbidden_names = {
        "_legacy_atomic_candidate_roles",
        "_best_clause_role_for_span",
        "understand_query_structure",
    }

    defined_functions = {
        node.name
        for node in tree.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    referenced_names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    forbidden_definitions = (
        forbidden_names
        & defined_functions
    )

    forbidden_references = (
        forbidden_names
        & referenced_names
    )

    assert not forbidden_definitions, (
        "Retired grammatical-role authorities "
        f"were redefined: "
        f"{sorted(forbidden_definitions)}"
    )

    assert not forbidden_references, (
        "Resolver regained an independent "
        "grammatical-role path: "
        f"{sorted(forbidden_references)}"
    )

    structural_calls = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "_structural_role_for_occurrence"
        )
    ]

    assert len(structural_calls) == 2, (
        "Expected exactly two production calls to the "
        "single occurrence-level role authority: "
        "constituent composition and generated-span role."
    )

    resolve_function = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name
                == "resolve_concept_span"
            )
        ),
        None,
    )

    assert resolve_function is not None

    resolve_args = {
        argument.arg
        for argument in (
            list(
                resolve_function.args.args
            )
            + list(
                resolve_function.args.kwonlyargs
            )
        )
    }

    assert "clause_role" in resolve_args

    resolver_role_rederivations = [
        node
        for node in ast.walk(
            resolve_function
        )
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "_structural_role_for_occurrence"
        )
    ]

    assert not resolver_role_rederivations, (
        "resolve_concept_span must preserve the "
        "generated role, not derive grammar again."
    )


# =========================================================
# A.7T1c2p — CANDIDATE COHESION PRIMITIVE
#
# Cohesion observes raw omission boundaries only. It does not
# infer phrase type, grammatical head, or semantic relation.
# =========================================================


def _cohesive_run_surfaces(query):
    segments = qcr._candidate_segments(query)

    return [
        [
            [
                candidate.surface_form
                for candidate in run
            ]
            for run in qcr._candidate_cohesive_runs(
                query,
                segment,
            )
        ]
        for segment in segments
    ]


@pytest.mark.parametrize(
    "query, expected",
    [
        (
            "DevOps observability dashboard project",
            [
                [
                    [
                        "DevOps",
                        "observability",
                        "dashboard",
                    ]
                ]
            ],
        ),
        (
            "monitoring dashboard project",
            [
                [
                    [
                        "monitoring",
                        "dashboard",
                    ]
                ]
            ],
        ),
        (
            "testing framework project",
            [
                [
                    [
                        "testing",
                        "framework",
                    ]
                ]
            ],
        ),
        (
            "Zorvex blenko project",
            [
                [
                    [
                        "Zorvex",
                        "blenko",
                    ]
                ]
            ],
        ),
    ],
)
def test_candidate_cohesion_preserves_whitespace_only_runs(
    query,
    expected,
):
    assert _cohesive_run_surfaces(query) == expected


@pytest.mark.parametrize(
    "query, expected",
    [
        (
            "reviewing a React project",
            [
                [
                    ["reviewing"],
                    ["React"],
                ]
            ],
        ),
        (
            "testing a React project",
            [
                [
                    ["testing"],
                    ["React"],
                ]
            ],
        ),
        (
            "seeking a React project",
            [
                [
                    ["seeking"],
                    ["React"],
                ]
            ],
        ),
        (
            "looking into a React project",
            [
                [
                    [
                        "looking",
                        "into",
                    ],
                    ["React"],
                ]
            ],
        ),
    ],
)
def test_candidate_cohesion_splits_on_non_whitespace_gap(
    query,
    expected,
):
    assert _cohesive_run_surfaces(query) == expected


@pytest.mark.parametrize(
    "query, expected_run",
    [
        (
            "testing React project",
            [
                "testing",
                "React",
            ],
        ),
        (
            "reviewing React project",
            [
                "reviewing",
                "React",
            ],
        ),
        (
            "seeking React project",
            [
                "seeking",
                "React",
            ],
        ),
        (
            "seeking information about React project",
            [
                "seeking",
                "information",
                "about",
                "React",
            ],
        ),
    ],
)
def test_candidate_cohesion_does_not_claim_articleless_syntax(
    query,
    expected_run,
):
    runs = _cohesive_run_surfaces(query)

    assert runs == [
        [
            expected_run,
        ]
    ]


# =========================================================
# A.7T1c2b2 — COHESIVE TERSE PROJECT FALLBACK
#
# The weak terminal-project fallback may assign GOAL only when
# its candidate segment is one raw-text-cohesive run.
#
# This is a precision guard, not a syntax parser. Article-less
# verbal/nominal ambiguity remains intentionally unresolved here.
# =========================================================


@pytest.mark.parametrize(
    "query",
    [
        "looking at a React project",
        "looking into a React project",
        "looking through a React project",
        "searching inside a React project",
        "reviewing a React project",
        "testing a React project",
        "seeking information about a React project",
        "seeking advice about a React project",
        "seeking examples of a React project",
    ],
)
def test_terse_project_fallback_rejects_split_candidate_runs(
    query,
):
    rows = _production_role_rows(query)

    assert rows
    assert all(
        row["role"] != "goal"
        for row in rows
    )


def test_terse_project_fallback_still_rejects_seeking_split_run():
    query = "seeking a React project"

    segments = qcr._candidate_segments(query)

    assert len(segments) == 1

    runs = qcr._candidate_cohesive_runs(
        query,
        segments[0],
    )

    assert [
        [
            candidate.surface_form
            for candidate in run
        ]
        for run in runs
    ] == [
        ["seeking"],
        ["React"],
    ]

    for char_span in (
        (0, 7),
        (10, 15),
        (0, 15),
    ):
        assert (
            qcr._terse_nominal_goal_for_occurrence(
                query,
                char_span=char_span,
                segment_index=0,
            )
            == qcr.ClauseRole.UNKNOWN
        )

    # c2b1 may still assign GOAL through its stronger explicit
    # bounded cue. This test protects the fallback path only.
    cues = qcr._role_cue_occurrences(query)

    assert any(
        cue[3] == "seeking_project"
        and cue[2] == qcr.ClauseRole.GOAL
        for cue in cues
    )


@pytest.mark.parametrize(
    "query",
    [
        "React project",
        "a React project",
        "an AI project",
        "the DevOps dashboard project",
        "DevOps observability dashboard project",
        "MLOps experiment tracking project",
        "FinTech fraud detection project",
        "AR VR education project",
        "monitoring dashboard project",
        "testing framework project",
        "Zorvex blenko project",
    ],
)
def test_terse_project_fallback_preserves_cohesive_nominal_requests(
    query,
):
    rows = _production_role_rows(query)

    assert rows
    assert all(
        row["role"] == "goal"
        for row in rows
    )


@pytest.mark.parametrize(
    "query",
    [
        "seeking React project",
        "reviewing React project",
        "testing React project",
        "looking into React project",
        "seeking information about React project",
    ],
)
def test_terse_project_cohesion_does_not_claim_articleless_syntax(
    query,
):
    segments = qcr._candidate_segments(query)

    assert len(segments) == 1

    runs = qcr._candidate_cohesive_runs(
        query,
        segments[0],
    )

    assert len(runs) == 1


# =========================================================
# A.7T1a — TERSE NOMINAL PROJECT REQUEST
#
# A terminal structural "project" head may establish GOAL
# intent without identifying or resolving the technical domain.
# =========================================================


@pytest.mark.parametrize(
    "query",
    [
        "DevOps observability dashboard project",
        "MLOps experiment tracking project",
    ],
)
def test_terse_nominal_project_assigns_goal_to_content(
    query,
):
    rows = _production_role_rows(query)

    assert rows
    assert all(
        row["role"] == "goal"
        for row in rows
    )


@pytest.mark.parametrize(
    "query",
    [
        "FinTech fraud detection project",
        "AR VR education project",
    ],
)
def test_terse_nominal_project_generalizes_to_held_out_domains(
    query,
):
    rows = _production_role_rows(query)

    assert rows
    assert all(
        row["role"] == "goal"
        for row in rows
    )


def test_terse_nominal_project_is_open_world():
    rows = _production_role_rows(
        "Zorvex blenko project"
    )

    roles = {
        row["normalized"]: row["role"]
        for row in rows
    }

    assert roles["zorvex"] == "goal"
    assert roles["blenko"] == "goal"
    assert roles["zorvex blenko"] == "goal"


def test_terse_nominal_project_does_not_cross_skill_held_scope():
    rows = _production_role_rows(
        "I know React for my project"
    )

    react = [
        row
        for row in rows
        if row["normalized"] == "react"
    ]

    assert react
    assert all(
        row["role"] == "skill_held"
        for row in react
    )


def test_terse_nominal_project_does_not_override_skill_target():
    rows = _production_role_rows(
        "learn Kubernetes for a project"
    )

    kubernetes = [
        row
        for row in rows
        if row["normalized"] == "kubernetes"
    ]

    assert kubernetes
    assert all(
        row["role"] == "skill_target"
        for row in kubernetes
    )


def test_terse_nominal_project_does_not_override_stack_preference():
    rows = _production_role_rows(
        "using FastAPI for the project"
    )

    fastapi = [
        row
        for row in rows
        if row["normalized"] == "fastapi"
    ]

    assert fastapi
    assert all(
        row["role"] == "stack_preference"
        for row in fastapi
    )


@pytest.mark.parametrize(
    "query",
    [
        "my current project uses React",
        "compare React and Vue project structures",
        "python react ai",
    ],
)
def test_non_request_terse_input_does_not_gain_goal_from_project(
    query,
):
    rows = _production_role_rows(query)

    assert not any(
        row["role"] == "goal"
        for row in rows
    )


def test_project_manager_role_does_not_gain_terse_goal():
    rows = _production_role_rows(
        "project manager role"
    )

    assert not any(
        row["role"] == "goal"
        for row in rows
    )


def test_existing_frontend_role_boundary_is_preserved():
    rows = _production_role_rows(
        "React portfolio project for frontend roles"
    )

    frontend = [
        row
        for row in rows
        if row["normalized"] == "frontend"
    ]

    assert frontend
    assert all(
        row["role"] == "role"
        for row in frontend
    )


def test_existing_cued_control_roles_are_unchanged():
    rows = _production_role_rows(
        "I know React but want a DevOps "
        "observability dashboard project"
    )

    react_roles = {
        row["role"]
        for row in rows
        if row["normalized"] == "react"
    }

    devops_roles = {
        row["role"]
        for row in rows
        if row["normalized"] == "devops"
    }

    assert react_roles == {
        "skill_held",
    }

    assert devops_roles == {
        "goal",
    }


def test_postposed_want_does_not_activate_terse_project_goal():
    rows = _production_role_rows(
        "react i used before now ml project want"
    )

    ml = [
        row
        for row in rows
        if row["normalized"] == "ml"
    ]

    assert ml
    assert all(
        row["role"] == "unknown"
        for row in ml
    )

@pytest.mark.parametrize(
    "query",
    [
        "I worked on a React project",
        "I have worked on a React project",
        "I previously worked on a React project",
        "I built a React project",
        "I created a React project",
        "I developed a React project",
        "My previous React project",
        "worked for a React project",
    ],
)
def test_terse_project_fallback_rejects_non_nominal_clause_framing(
    query,
):
    rows = _production_role_rows(query)

    assert not any(
        row["role"] == "goal"
        for row in rows
    )


@pytest.mark.parametrize(
    "query",
    [
        "React project",
        "a React project",
        "an AI project",
        "the DevOps dashboard project",
        "DevOps observability dashboard project",
        "MLOps experiment tracking project",
        "FinTech fraud detection project",
        "AR VR education project",
        "Zorvex blenko project",
    ],
)
def test_terse_project_fallback_accepts_clause_initial_nominal_frame(
    query,
):
    rows = _production_role_rows(query)

    assert any(
        row["role"] == "goal"
        for row in rows
    )


@pytest.mark.parametrize(
    "query, normalized",
    [
        (
            "I am comfortable with Python",
            "python",
        ),
        (
            "I am familiar with React",
            "react",
        ),
    ],
)
def test_multiword_role_cue_can_cross_segment_left_scope_inside_same_cue(
    query,
    normalized,
):
    rows = _production_role_rows(query)

    matches = [
        row
        for row in rows
        if row["normalized"] == normalized
    ]

    assert matches
    assert all(
        row["role"] == "skill_held"
        for row in matches
    )


@pytest.mark.parametrize(
    "query, normalized",
    [
        (
            "I worked on Python for a React project",
            "react",
        ),
        (
            "I worked on a React project",
            "react",
        ),
    ],
)
def test_cross_segment_cue_repair_does_not_reopen_stale_cue_scope(
    query,
    normalized,
):
    rows = _production_role_rows(query)

    matches = [
        row
        for row in rows
        if row["normalized"] == normalized
    ]

    assert matches
    assert all(
        row["role"] == "unknown"
        for row in matches
    )


def test_looking_for_project_is_owned_by_explicit_goal_cue():
    query = "looking for a React project"

    cues = qcr._role_cue_occurrences(query)

    request_cues = [
        cue
        for cue in cues
        if cue[3] == "looking_for"
    ]

    assert len(request_cues) == 1

    start, end, role, _ = request_cues[0]

    assert query[start:end] == "looking for"
    assert role == qcr.ClauseRole.GOAL

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


@pytest.mark.parametrize(
    "query, normalized",
    [
        (
            "looking for a React project",
            "react",
        ),
        (
            "I am looking for a React project",
            "react",
        ),
        (
            "searching for a React project",
            "react",
        ),
        (
            "I am searching for a React project",
            "react",
        ),
        (
            "looking for a Zorvex project",
            "zorvex",
        ),
        (
            "searching for a Zorvex project",
            "zorvex",
        ),
    ],
)
def test_explicit_request_cues_assign_goal_to_requested_concept(
    query,
    normalized,
):
    rows = _production_role_rows(query)

    matches = [
        row
        for row in rows
        if row["normalized"] == normalized
    ]

    assert matches
    assert all(
        row["role"] == "goal"
        for row in matches
    )


@pytest.mark.parametrize(
    "query, cue_name, expected_text",
    [
        (
            "looking for a React project",
            "looking_for",
            "looking for",
        ),
        (
            "I am looking for a React project",
            "looking_for",
            "looking for",
        ),
        (
            "searching for a React project",
            "searching_for",
            "searching for",
        ),
        (
            "I am searching for a React project",
            "searching_for",
            "searching for",
        ),
    ],
)
def test_explicit_request_cue_occurrence_includes_request_verb(
    query,
    cue_name,
    expected_text,
):
    cues = qcr._role_cue_occurrences(query)

    matches = [
        cue
        for cue in cues
        if cue[3] == cue_name
    ]

    assert len(matches) == 1

    start, end, role, _ = matches[0]

    assert query[start:end].lower() == expected_text
    assert role == qcr.ClauseRole.GOAL


@pytest.mark.parametrize(
    "query",
    [
        "looking at a React project",
        "looking into a React project",
        "looking through a React project",
        "searching inside a React project",
    ],
)
def test_non_request_look_search_forms_do_not_gain_explicit_goal_cue(
    query,
):
    goal_cue_names = {
        cue_name
        for _, _, role, cue_name
        in qcr._role_cue_occurrences(query)
        if role == qcr.ClauseRole.GOAL
    }

    assert "looking_for" not in goal_cue_names
    assert "searching_for" not in goal_cue_names


def test_later_request_cue_owns_goal_after_earlier_held_skill():
    rows = _production_role_rows(
        "I know React but am looking for an AI project"
    )

    react = [
        row
        for row in rows
        if row["normalized"] == "react"
    ]

    ai = [
        row
        for row in rows
        if row["normalized"] == "ai"
    ]

    assert react
    assert ai

    assert all(
        row["role"] == "skill_held"
        for row in react
    )

    assert all(
        row["role"] == "goal"
        for row in ai
    )


@pytest.mark.parametrize(
    "query",
    [
        (
            "I use Python and am looking for "
            "a data engineering project"
        ),
        (
            "I use Python and am searching for "
            "a data engineering project"
        ),
    ],
)
def test_later_request_cue_owns_goal_after_earlier_stack_scope(
    query,
):
    rows = _production_role_rows(query)

    python_rows = [
        row
        for row in rows
        if row["normalized"] == "python"
    ]

    data_engineering = [
        row
        for row in rows
        if row["normalized"] == "data engineering"
    ]

    assert python_rows
    assert data_engineering

    assert all(
        row["role"] == "stack_preference"
        for row in python_rows
    )

    assert all(
        row["role"] == "goal"
        for row in data_engineering
    )



@pytest.mark.parametrize(
    "query",
    [
        "I want to use Python for a data engineering project",
        "use Python for a data engineering project",
        "using Python for a data engineering project",
    ],
)
def test_stack_governed_project_complement_becomes_goal(
    query,
):
    rows = _production_role_rows(query)

    data_engineering = [
        row
        for row in rows
        if row["normalized"]
        == "data engineering"
    ]

    assert data_engineering
    assert all(
        row["role"] == "goal"
        for row in data_engineering
    )


@pytest.mark.parametrize(
    ("query", "concept"),
    [
        (
            "worked for a React project",
            "react",
        ),
        (
            "I worked for a React project",
            "react",
        ),
        (
            "I worked on Python for a React project",
            "react",
        ),
    ],
)
def test_for_project_frame_requires_stack_governed_predecessor(
    query,
    concept,
):
    rows = _production_role_rows(query)

    matches = [
        row
        for row in rows
        if row["normalized"] == concept
    ]

    assert matches
    assert all(
        row["role"] == "unknown"
        for row in matches
    )


# =========================================================
# A.7T1c2b1 — BOUNDED SEEKING PROJECT CUE
#
# "seeking" becomes a GOAL cue only for the bounded structural
# construction:
#
#   seeking + article + cohesive content + terminal project
#
# The cue producer observes structure only. It does not inspect
# concept identity, evidence, taxonomy, or existing role output.
# =========================================================


@pytest.mark.parametrize(
    "query, normalized",
    [
        (
            "seeking a React project",
            "react",
        ),
        (
            "I am seeking a React project",
            "react",
        ),
        (
            "seeking a Zorvex project",
            "zorvex",
        ),
        (
            "seeking an AR VR education project",
            "education",
        ),
    ],
)
def test_bounded_seeking_project_assigns_goal_to_requested_content(
    query,
    normalized,
):
    cues = qcr._role_cue_occurrences(query)

    seeking_cues = [
        cue
        for cue in cues
        if cue[3] == "seeking_project"
    ]

    assert len(seeking_cues) == 1

    start, end, role, _ = seeking_cues[0]

    assert query[start:end].lower() == "seeking"
    assert role == qcr.ClauseRole.GOAL

    rows = _production_role_rows(query)

    matches = [
        row
        for row in rows
        if row["normalized"] == normalized
    ]

    assert matches
    assert all(
        row["role"] == "goal"
        for row in matches
    )


@pytest.mark.parametrize(
    "query",
    [
        "seeking information about a React project",
        "seeking advice about a React project",
        "seeking examples of a React project",
        "seeking help with a React project",
        "seeking a mentor",
        "seeking an internship",
        "seeking a group project partner",
        "seeking a project",
        "seeking a React project for my portfolio",
    ],
)
def test_bounded_seeking_project_rejects_non_bounded_frames(
    query,
):
    cues = qcr._role_cue_occurrences(query)

    assert not any(
        cue[3] == "seeking_project"
        for cue in cues
    )


def test_bounded_seeking_project_preserves_held_skill_before_contrast():
    query = (
        "I know React but am seeking an AI project"
    )

    rows = _production_role_rows(query)

    react = [
        row
        for row in rows
        if row["normalized"] == "react"
    ]

    ai = [
        row
        for row in rows
        if row["normalized"] == "ai"
    ]

    assert react
    assert ai

    assert all(
        row["role"] == "skill_held"
        for row in react
    )

    assert all(
        row["role"] == "goal"
        for row in ai
    )


def test_bounded_seeking_project_supersedes_older_stack_scope_for_request():
    query = (
        "I use Python and am seeking "
        "a data engineering project"
    )

    rows = _production_role_rows(query)

    python_rows = [
        row
        for row in rows
        if row["normalized"] == "python"
    ]

    data_engineering = [
        row
        for row in rows
        if row["normalized"]
        == "data engineering"
    ]

    assert python_rows
    assert data_engineering

    assert all(
        row["role"] == "stack_preference"
        for row in python_rows
    )

    assert all(
        row["role"] == "goal"
        for row in data_engineering
    )


def test_bounded_seeking_project_does_not_overlap_later_specialized_cue():
    query = "seeking a DSA practice project"

    cues = qcr._role_cue_occurrences(query)

    cue_names = [
        cue[3]
        for cue in cues
    ]

    assert "seeking_project" not in cue_names
    assert "practice" in cue_names


@pytest.mark.parametrize(
    "query",
    [
        "seeking React project",
        "seeking information about React project",
    ],
)
def test_bounded_seeking_project_does_not_claim_articleless_ambiguity(
    query,
):
    cues = qcr._role_cue_occurrences(query)

    assert not any(
        cue[3] == "seeking_project"
        for cue in cues
    )


def test_synthesized_seeking_cue_is_pre_role_only():
    path = Path(
        "src/query_concept_resolution.py"
    )

    tree = ast.parse(
        path.read_text(
            encoding="utf-8"
        ),
        filename=str(path),
    )

    helper = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name
                == "_bounded_seeking_project_cues"
            )
        ),
        None,
    )

    assert helper is not None

    forbidden_calls = {
        "_structural_role_for_occurrence",
        "_segment_bounded_role_for_occurrence",
        "_cue_scope_role_for_occurrence",
        "_bounded_role_for_occurrence",
        "_role_morphology_for_occurrence",
        "resolve_concept_span",
        "resolve_query_spans_shadow",
    }

    helper_calls = {
        node.func.id
        for node in ast.walk(helper)
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
        )
    }

    assert not (
        helper_calls
        & forbidden_calls
    ), (
        "Synthesized cue construction must "
        "remain pre-role structural logic."
    )



def test_a7t2_cross_family_focus_does_not_inherit_family_authority(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Cloud observability pattern",
            category="cloud",
            focus="cloud",
            family="cloud_platform",
            score=0.90,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="MLOps observability pattern",
            category="mlops",
            focus="mlops",
            family="ai_ml",
            score=0.60,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="AI observability research",
            category="ai_ml",
            focus="ai_ml",
            family="ai_ml",
            score=0.60,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: hits,
    )

    result = qcr.resolve_concept_span(
        "observability",
        query="observability project",
        char_span=(0, 13),
        constituent_char_spans=((0, 13),),
        segment_index=0,
        clause_role=ClauseRole.GOAL,
    )

    # A.7E disproved the old source-diversity assumption:
    # two records that disagree at focus level do not become
    # authoritative merely because they share a taxonomy parent
    # and originate from different source types. The winning
    # family has only two distinct attributable records here,
    # below the existing support floor of three.
    assert (
        result.resolution_status
        == qcr.ResolutionStatus.SUPPORTED_WEAK
    )
    assert result.inferred_family == "ai_ml"
    assert result.inferred_focus is None



def test_a7e1_losing_family_evidence_cannot_grant_winner_authority(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    winner_hit = qcr.ConceptEvidenceHit(
        source_type="project_pattern",
        title="Cloud observability pattern",
        category="cloud",
        focus="cloud",
        family="cloud_platform",
        score=0.90,
        lexical_match=True,
        lexical_coverage=1.0,
        bm25_score=None,
    )

    losing_hits = [
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="AI evidence A",
            category="ai_ml",
            focus="ai_ml",
            family="ai_ml",
            score=0.30,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=6.0,
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="AI evidence B",
            category="ai_ml",
            focus="ai_ml",
            family="ai_ml",
            score=0.20,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
        ),
    ]

    def resolve(hits):
        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            lambda *args, **kwargs: list(hits),
        )

        return qcr.resolve_concept_span(
            "observability",
            query="observability project",
            clause_role=ClauseRole.GOAL,
        )

    winner_only = resolve([winner_hit])

    winner_plus_losers = resolve(
        [
            winner_hit,
            *losing_hits,
        ]
    )

    assert winner_only.inferred_family == "cloud_platform"
    assert (
        winner_only.resolution_status
        == qcr.ResolutionStatus.SUPPORTED_WEAK
    )

    assert (
        winner_plus_losers.inferred_family
        == "cloud_platform"
    )

    # Evidence attributable only to competing families must not
    # manufacture classification authority for the winner.
    assert (
        winner_plus_losers.resolution_status
        == winner_only.resolution_status
    )




def test_a7e3_full_rag_phrase_qualifies_rag_abbreviation_evidence():
    """
    Canonical abbreviation/expansion equivalence belongs to lexical
    qualification.

    It does not assign a domain. It only prevents evidence written
    with the equivalent surface form from being discarded.
    """
    import query_concept_resolution as qcr

    item = {
        "title": "RAG Evaluation Dashboard",
        "abstract": (
            "Evaluate RAG systems with retrieval quality, faithfulness, "
            "citation coverage, and answer-quality metrics."
        ),
        "category": "rag_llm",
    }

    assert qcr._lexical_match(
        "retrieval augmented generation",
        item,
    )

    assert (
        qcr._lexical_coverage(
            "retrieval augmented generation",
            item,
        )
        == 1.0
    )


def test_a7e3_rag_abbreviation_qualifies_full_phrase_evidence():
    """
    Lexical equivalence is symmetric for evidence qualification.
    """
    import query_concept_resolution as qcr

    item = {
        "title": (
            "Evaluation of Retrieval Augmented Generation "
            "for Question Answering"
        ),
        "abstract": (
            "Retrieval augmented generation combines retrieval with "
            "generation for grounded question answering."
        ),
        "category": "cs.CL",
    }

    assert qcr._lexical_match(
        "RAG",
        item,
    )

    assert (
        qcr._lexical_coverage(
            "RAG",
            item,
        )
        == 1.0
    )


def test_a7e3_lexical_equivalence_does_not_assign_domain_authority(
    monkeypatch,
):
    """
    Equivalent vocabulary can expose matching evidence but cannot
    lower the absolute family-authority support floor.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="RAG Evaluation Dashboard",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag-eval",
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="example/rag-tool",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.65,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="github_repository:rag-tool",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "retrieval augmented generation",
        query="retrieval augmented generation project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.SUPPORTED_WEAK
    )


def test_a7e3_rag_alias_and_full_phrase_share_one_canonical_focus(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="RAG Evaluation Dashboard",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.60,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag-eval",
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="example/rag-tool",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.55,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="github_repository:rag-tool",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="RAG Research",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.50,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=8.0,
            evidence_id="research_paper:rag",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    short = qcr.resolve_concept_span(
        "RAG",
        query="RAG project",
        clause_role=ClauseRole.GOAL,
    )

    full = qcr.resolve_concept_span(
        "retrieval augmented generation",
        query="retrieval augmented generation project",
        clause_role=ClauseRole.GOAL,
    )

    assert short.inferred_family == "ai_ml"
    assert full.inferred_family == "ai_ml"

    assert short.inferred_focus == "rag_llm"
    assert full.inferred_focus == "rag_llm"



def test_a7e3_focus_election_caps_repeated_source_contributions(
    monkeypatch,
):
    """
    Family and focus election must use the same provenance-aware
    score aggregation.

    Distinct records still count toward the absolute authority floor,
    but repeated records from one source type must not receive
    unbounded voting weight during focus competition.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="RAG Pattern",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.55,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag",
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="example/rag",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.54,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="github_repository:rag",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Research A",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=10.0,
            evidence_id="research_paper:a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Research B",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.69,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=9.0,
            evidence_id="research_paper:b",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Research C",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.68,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=8.0,
            evidence_id="research_paper:c",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "RAG",
        query="RAG project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "ai_ml"

    # Project + GitHub independently support rag_llm.
    # Three records from the research corpus must not receive three
    # separate voting units merely because focus scoring descended
    # one taxonomy level.
    assert result.inferred_focus == "rag_llm"




def test_a7e5_conflicting_duplicate_identity_cannot_gain_domain_authority(
    monkeypatch,
):
    """
    One canonical evidence identity cannot acquire its semantic
    classification from whichever duplicate representation has the
    larger retrieval score.

    Conflicting family/focus metadata for one identity is a data
    integrity conflict. That identity may prove lexical existence,
    but it must fail closed for domain authority.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    stable_hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Stable DevOps A",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:stable-a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Stable DevOps B",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.65,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:stable-b",
        ),
    ]

    conflicting_identity = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Conflicting Record",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.40,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:conflict",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Conflicting Record",
            category="ai_ml",
            focus="ai_ml",
            family="ai_ml",
            score=0.80,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:conflict",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: (
            stable_hits
            + conflicting_identity
        ),
    )

    result = qcr.resolve_concept_span(
        "DevOps",
        query="DevOps project",
        clause_role=ClauseRole.GOAL,
    )

    # Only two non-conflicting cloud records remain semantically
    # trustworthy. The conflicted canonical identity must not become
    # either a cloud vote or an AI vote merely because one duplicate
    # has the higher retrieval score.
    assert (
        result.resolution_status
        == qcr.ResolutionStatus.SUPPORTED_WEAK
    )

    assert result.inferred_family == "cloud_platform"
    assert result.inferred_focus == "devops"


def test_a7e5_conflicting_identity_is_score_invariant(
    monkeypatch,
):
    """
    Changing retrieval scores between conflicting representations of
    one canonical identity must not change the semantic conclusion.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    stable_hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Stable DevOps A",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:stable-a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Stable DevOps B",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.65,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:stable-b",
        ),
    ]

    def conflicting(
        cloud_score,
        ai_score,
    ):
        return [
            qcr.ConceptEvidenceHit(
                source_type="project_pattern",
                title="Conflicting Record",
                category="devops",
                focus="devops",
                family="cloud_platform",
                score=cloud_score,
                lexical_match=True,
                lexical_coverage=1.0,
                bm25_score=None,
                evidence_id="project_pattern:conflict",
            ),
            qcr.ConceptEvidenceHit(
                source_type="project_pattern",
                title="Conflicting Record",
                category="ai_ml",
                focus="ai_ml",
                family="ai_ml",
                score=ai_score,
                lexical_match=True,
                lexical_coverage=1.0,
                bm25_score=None,
                evidence_id="project_pattern:conflict",
            ),
        ]

    def resolve(extra):
        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            lambda *args, **kwargs: (
                stable_hits
                + extra
            ),
        )

        return qcr.resolve_concept_span(
            "DevOps",
            query="DevOps project",
            clause_role=ClauseRole.GOAL,
        )

    cloud_high = resolve(
        conflicting(
            cloud_score=0.90,
            ai_score=0.20,
        )
    )

    ai_high = resolve(
        conflicting(
            cloud_score=0.20,
            ai_score=0.90,
        )
    )

    assert (
        cloud_high.resolution_status
        == ai_high.resolution_status
    )
    assert (
        cloud_high.inferred_family
        == ai_high.inferred_family
    )
    assert (
        cloud_high.inferred_focus
        == ai_high.inferred_focus
    )
    assert (
        cloud_high.confidence
        == ai_high.confidence
    )


def test_a7e4_losing_family_records_cannot_inflate_confidence(
    monkeypatch,
):
    """
    Confidence support must be attributable to the elected family.

    The two resolutions below have:
      - identical winning-family evidence,
      - the same elected family,
      - the same strongest competing-family score,
      - therefore the same family margin.

    Adding another losing-family record/source must not increase
    confidence through whole-pool hit count or source diversity.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    winner_hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Cloud Winner A",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.80,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:winner-a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Cloud Winner B",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.75,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:winner-b",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Cloud Winner C",
            category="devops",
            focus="devops",
            family="cloud_platform",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:winner-c",
        ),
    ]

    strongest_loser = qcr.ConceptEvidenceHit(
        source_type="research_paper",
        title="AI Loser",
        category="cs.LG",
        focus="ai_ml",
        family="ai_ml",
        score=0.20,
        lexical_match=True,
        lexical_coverage=1.0,
        bm25_score=4.0,
        evidence_id="research_paper:loser",
    )

    additional_loser = qcr.ConceptEvidenceHit(
        source_type="github_repository",
        title="Frontend Loser",
        category="frontend",
        focus="frontend",
        family="software_engineering",
        score=0.10,
        lexical_match=True,
        lexical_coverage=1.0,
        bm25_score=None,
        evidence_id="github_repository:loser",
    )

    def resolve(hits):
        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            lambda *args, **kwargs: list(hits),
        )

        return qcr.resolve_concept_span(
            "DevOps",
            query="DevOps project",
            clause_role=ClauseRole.GOAL,
        )

    baseline = resolve(
        winner_hits
        + [strongest_loser]
    )

    contaminated = resolve(
        winner_hits
        + [
            strongest_loser,
            additional_loser,
        ]
    )

    assert (
        baseline.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert (
        contaminated.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )

    assert baseline.inferred_family == "cloud_platform"
    assert contaminated.inferred_family == "cloud_platform"

    baseline_scores = qcr._domain_scores(
        winner_hits
        + [strongest_loser]
    )
    contaminated_scores = qcr._domain_scores(
        winner_hits
        + [
            strongest_loser,
            additional_loser,
        ]
    )

    baseline_family, baseline_margin = qcr._best_and_margin(
        baseline_scores
    )
    contaminated_family, contaminated_margin = qcr._best_and_margin(
        contaminated_scores
    )

    assert baseline_family == contaminated_family
    assert baseline_family == "cloud_platform"

    # software_engineering=0.10 cannot displace ai_ml=0.20
    # as the strongest competitor, so competition is unchanged.
    assert baseline_margin == contaminated_margin

    # With winning support and competitive margin unchanged,
    # losing evidence has no positive confidence contribution.
    assert contaminated.confidence == baseline.confidence


def test_a7e3_broad_ai_label_does_not_force_family_named_child_focus(
    monkeypatch,
):
    """
    A broad family expression must not manufacture child specificity
    merely because the taxonomy contains a same-named focus.
    """
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="General AI Pattern",
            category="ai_ml",
            focus="ai_ml",
            family="ai_ml",
            score=0.60,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:general-ai",
        ),
        qcr.ConceptEvidenceHit(
            source_type="github_repository",
            title="MLOps Repository",
            category="mlops",
            focus="mlops",
            family="ai_ml",
            score=0.55,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="github_repository:mlops",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="NLP Research",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.54,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=8.0,
            evidence_id="research_paper:nlp",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "AI",
        query="AI project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "ai_ml"

    # "AI" is broad family-level language here. It must not force
    # the same-named ai_ml child focus over competing child readings.
    assert result.inferred_focus is None




def test_focus_authority_does_not_increase_when_competing_record_is_removed(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    def hit(
        *,
        evidence_id,
        focus,
        score,
    ):
        return qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title=evidence_id,
            category=focus,
            focus=focus,
            family="ai_ml",
            score=score,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id=evidence_id,
        )

    winner = [
        hit(
            evidence_id=f"a-{index}",
            focus="rag_llm",
            score=score,
        )
        for index, score in enumerate(
            (0.90, 0.80, 0.70),
            start=1,
        )
    ]

    competitor = [
        hit(
            evidence_id=f"b-{index}",
            focus="healthcare_ai",
            score=score,
        )
        for index, score in enumerate(
            (0.85, 0.75, 0.65),
            start=1,
        )
    ]

    populations = (
        winner + competitor,
        winner + competitor[:2],
    )

    results = []

    for evidence in populations:
        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            lambda *args, evidence=evidence, **kwargs: list(evidence),
        )

        results.append(
            qcr.resolve_concept_span(
                "grounded assistant",
                query="grounded assistant project",
                clause_role=ClauseRole.GOAL,
            )
        )

    full, reduced = results

    assert full.inferred_family == "ai_ml"
    assert reduced.inferred_family == "ai_ml"

    # Removing a non-max competing record leaves source-capped
    # election scores unchanged. It must therefore not turn
    # abstention into more specific focus authority.
    assert full.inferred_focus is None
    assert reduced.inferred_focus is None


def test_research_subject_category_does_not_override_specific_project_focus(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Retrieval Grounded Assistant",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.52,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag-a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Grounded Generation Evaluator",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.48,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag-b",
        ),
        qcr.ConceptEvidenceHit(
            source_type="project_pattern",
            title="Retrieval Pipeline Inspector",
            category="rag_llm",
            focus="rag_llm",
            family="ai_ml",
            score=0.44,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="project_pattern:rag-c",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Retrieval Grounded Language Study",
            category="cs.CL",
            focus="nlp",
            family="ai_ml",
            score=0.70,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="research_paper:subject-a",
        ),
        qcr.ConceptEvidenceHit(
            source_type="research_paper",
            title="Information Retrieval Study",
            category="cs.IR",
            focus="recommendation_systems",
            family="ai_ml",
            score=0.68,
            lexical_match=True,
            lexical_coverage=1.0,
            bm25_score=None,
            evidence_id="research_paper:subject-b",
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "retrieval augmented generation",
        query="retrieval augmented generation project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "ai_ml"
    assert result.inferred_focus == "rag_llm"

def _a7e_hit(
    *,
    source_type,
    title,
    focus,
    family,
    score,
):
    import query_concept_resolution as qcr

    return qcr.ConceptEvidenceHit(
        source_type=source_type,
        title=title,
        category=focus,
        focus=focus,
        family=family,
        score=score,
        lexical_match=True,
        lexical_coverage=1.0,
        bm25_score=None,
    )


def test_a7e2_distinct_same_source_records_can_establish_family_authority(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        _a7e_hit(
            source_type="project_pattern",
            title="CI/CD Failure Intelligence Platform",
            focus="devops",
            family="cloud_platform",
            score=0.55,
        ),
        _a7e_hit(
            source_type="project_pattern",
            title="Incident Postmortem Generator",
            focus="devops",
            family="cloud_platform",
            score=0.54,
        ),
        _a7e_hit(
            source_type="project_pattern",
            title="Deployment Risk Scoring System",
            focus="devops",
            family="cloud_platform",
            score=0.50,
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "DevOps",
        query="DevOps project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "cloud_platform"
    assert result.inferred_focus == "devops"


def test_a7e2_duplicate_records_do_not_satisfy_distinct_support_floor(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    duplicate = _a7e_hit(
        source_type="project_pattern",
        title="Same Project Pattern",
        focus="devops",
        family="cloud_platform",
        score=0.90,
    )

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: [
            duplicate,
            duplicate,
            duplicate,
        ],
    )

    result = qcr.resolve_concept_span(
        "DevOps",
        query="DevOps project",
        clause_role=ClauseRole.GOAL,
    )

    # This is incidentally GREEN under the pre-A.7E2 implementation
    # because all duplicates share one source type. After source-type
    # diversity is removed from semantic authority, this contract
    # specifically guards against raw duplicate-count inflation.
    assert (
        result.resolution_status
        == qcr.ResolutionStatus.SUPPORTED_WEAK
    )


def test_a7e2_family_authority_can_survive_focus_ambiguity(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        _a7e_hit(
            source_type="project_pattern",
            title="MLOps Pattern A",
            focus="mlops",
            family="ai_ml",
            score=0.60,
        ),
        _a7e_hit(
            source_type="research_paper",
            title="AI Research B",
            focus="ai_ml",
            family="ai_ml",
            score=0.60,
        ),
        _a7e_hit(
            source_type="github_repository",
            title="NLP Repository C",
            focus="nlp",
            family="ai_ml",
            score=0.60,
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "observability",
        query="observability project",
        clause_role=ClauseRole.GOAL,
    )

    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "ai_ml"
    assert result.inferred_focus is None


def test_a7e2_single_focus_support_is_coherent_even_with_zero_margin(
    monkeypatch,
):
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    hits = [
        _a7e_hit(
            source_type="project_pattern",
            title="Data Pattern A",
            focus="data_engineering",
            family="cloud_platform",
            score=0.70,
        ),
        _a7e_hit(
            source_type="project_pattern",
            title="Data Pattern B",
            focus="data_engineering",
            family="cloud_platform",
            score=0.65,
        ),
        _a7e_hit(
            source_type="project_pattern",
            title="Data Pattern C",
            focus="data_engineering",
            family="cloud_platform",
            score=0.60,
        ),
    ]

    monkeypatch.setattr(
        qcr,
        "_collect_span_evidence",
        lambda *args, **kwargs: list(hits),
    )

    result = qcr.resolve_concept_span(
        "data engineering",
        query="data engineering project",
        clause_role=ClauseRole.GOAL,
    )

    assert result.domain_margin == 0.0
    assert (
        result.resolution_status
        == qcr.ResolutionStatus.EVIDENCE_RESOLVED
    )
    assert result.inferred_family == "cloud_platform"
    assert result.inferred_focus == "data_engineering"



def test_a7e5_resolved_focus_always_belongs_to_resolved_family_across_taxonomy(
    monkeypatch,
):
    """
    Any specific focus exposed by the resolver must belong to the
    resolver's elected family.

    Production evidence derives family from focus. This contract makes
    that hierarchy explicit so the invariant cannot silently disappear
    if evidence construction changes later.
    """
    import domain_taxonomy as taxonomy
    import query_concept_resolution as qcr
    from query_concept_understanding import ClauseRole

    for focus in sorted(
        taxonomy.FOCUS_TO_FAMILY
    ):
        family = taxonomy.get_domain_family(
            focus
        )

        if (
            focus == "general"
            or family == "general"
        ):
            continue

        hits = [
            qcr.ConceptEvidenceHit(
                source_type="project_pattern",
                title=(
                    f"{focus} coherence record {index}"
                ),
                category=focus,
                focus=focus,
                family=family,
                score=(
                    0.80
                    - (index * 0.05)
                ),
                lexical_match=True,
                lexical_coverage=1.0,
                bm25_score=None,
                evidence_id=(
                    f"project_pattern:"
                    f"{focus}:coherence:{index}"
                ),
            )
            for index in range(3)
        ]

        monkeypatch.setattr(
            qcr,
            "_collect_span_evidence",
            lambda *args, _hits=hits, **kwargs: (
                _hits
            ),
        )

        result = qcr.resolve_concept_span(
            focus.replace(
                "_",
                " ",
            ),
            query=(
                f"Build a "
                f"{focus.replace('_', ' ')} "
                f"project"
            ),
            clause_role=ClauseRole.GOAL,
        )

        assert (
            result.resolution_status
            == qcr.ResolutionStatus.EVIDENCE_RESOLVED
        )

        assert result.inferred_focus == focus
        assert result.inferred_family == family

        assert (
            result.inferred_focus is None
            or taxonomy.get_domain_family(
                result.inferred_focus
            )
            == result.inferred_family
        )
