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
        "seeking a React project",
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
