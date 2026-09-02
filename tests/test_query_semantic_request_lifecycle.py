from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _module_tree(relative_path: str):
    path = ROOT / relative_path
    return ast.parse(
        path.read_text(),
        filename=str(path),
    )


def _function_node(
    tree: ast.AST,
    name: str,
) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == name
        )
    ]

    assert len(matches) == 1, (
        name,
        len(matches),
    )

    return matches[0]


def _call_name(
    call: ast.Call,
):
    if isinstance(call.func, ast.Name):
        return call.func.id

    if isinstance(call.func, ast.Attribute):
        return call.func.attr

    return None


def _calls_named(
    node: ast.AST,
    name: str,
):
    return [
        call
        for call in ast.walk(node)
        if (
            isinstance(call, ast.Call)
            and _call_name(call) == name
        )
    ]


def _keyword_value_name(
    call: ast.Call,
    keyword_name: str,
):
    matches = [
        keyword
        for keyword in call.keywords
        if keyword.arg == keyword_name
    ]

    assert len(matches) == 1, (
        keyword_name,
        len(matches),
    )

    value = matches[0].value

    assert isinstance(value, ast.Name), (
        keyword_name,
        ast.dump(value),
    )

    return value.id


def test_product_request_builds_canonical_semantics_once():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    builders = _calls_named(
        handler,
        "build_query_semantic_snapshot",
    )

    assert len(builders) == 1


def test_same_snapshot_is_propagated_to_retrieval_and_generation():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    retrieval_calls = _calls_named(
        handler,
        "retrieve_evidence",
    )

    generation_calls = _calls_named(
        handler,
        "generate_project_ideas",
    )

    assert len(retrieval_calls) == 1
    assert len(generation_calls) == 1

    assert (
        _keyword_value_name(
            retrieval_calls[0],
            "semantic_snapshot",
        )
        == "semantic_snapshot"
    )

    assert (
        _keyword_value_name(
            generation_calls[0],
            "semantic_snapshot",
        )
        == "semantic_snapshot"
    )


def test_downstream_consumers_do_not_rebuild_query_semantics():
    source_router_tree = _module_tree(
        "src/source_router.py"
    )

    generator_tree = _module_tree(
        "src/project_idea_generator.py"
    )

    retrieve = _function_node(
        source_router_tree,
        "retrieve_evidence",
    )

    generate = _function_node(
        generator_tree,
        "generate_project_ideas",
    )

    assert not _calls_named(
        retrieve,
        "build_query_semantic_snapshot",
    )

    assert not _calls_named(
        generate,
        "build_query_semantic_snapshot",
    )


def test_downstream_semantic_snapshot_parameters_remain_optional():
    source_router_tree = _module_tree(
        "src/source_router.py"
    )

    generator_tree = _module_tree(
        "src/project_idea_generator.py"
    )

    retrieve = _function_node(
        source_router_tree,
        "retrieve_evidence",
    )

    generate = _function_node(
        generator_tree,
        "generate_project_ideas",
    )

    for function in (
        retrieve,
        generate,
    ):
        names = [
            arg.arg
            for arg in function.args.args
        ]

        assert "semantic_snapshot" in names

        defaults_by_name = dict(
            zip(
                names[
                    len(names)
                    - len(function.args.defaults):
                ],
                function.args.defaults,
            )
        )

        default = defaults_by_name[
            "semantic_snapshot"
        ]

        assert (
            isinstance(default, ast.Constant)
            and default.value is None
        )



def test_product_request_builds_planning_projection_once():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    builders = _calls_named(
        handler,
        "build_planning_semantic_projection",
    )

    assert len(builders) == 1

    assert (
        builders[0].args
        and isinstance(builders[0].args[0], ast.Name)
        and builders[0].args[0].id == "semantic_snapshot"
    )


def test_product_adapter_consumes_planning_projection_not_raw_query():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    typed_calls = _calls_named(
        handler,
        "adapt_ideas_to_planning_semantics",
    )

    legacy_calls = _calls_named(
        handler,
        "adapt_ideas_to_query_anchors",
    )

    assert len(typed_calls) == 1
    assert not legacy_calls

    assert (
        _keyword_value_name(
            typed_calls[0],
            "planning_semantics",
        )
        == "planning_semantics"
    )

    assert all(
        keyword.arg != "query"
        for keyword in typed_calls[0].keywords
    )


def test_typed_adapter_does_not_reparse_raw_query():
    tree = _module_tree(
        "src/planning/query_anchor_direction_adapter.py"
    )

    adapter = _function_node(
        tree,
        "adapt_ideas_to_planning_semantics",
    )

    assert not _calls_named(
        adapter,
        "extract_query_anchors",
    )

    argument_names = [
        arg.arg
        for arg in adapter.args.args
    ]

    assert "query" not in argument_names

def test_source_router_does_not_use_legacy_query_metadata_for_retrieval():
    tree = _module_tree(
        "src/source_router.py"
    )

    imported_modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(
                alias.name
                for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
        ):
            imported_modules.add(node.module)

    assert "query_expander" not in imported_modules

    retrieve = _function_node(
        tree,
        "retrieve_evidence",
    )

    assert not _calls_named(
        retrieve,
        "get_query_metadata",
    )


def test_product_retrieval_hints_use_understanding_not_correction_metadata():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    retrieval_calls = _calls_named(
        handler,
        "retrieve_evidence",
    )

    assert len(retrieval_calls) == 1

    assignments = [
        node
        for node in ast.walk(handler)
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "retrieval_intent_hints"
                for target in node.targets
            )
        )
    ]

    assert len(assignments) == 1

    assigned_value = assignments[0].value

    referenced_names = {
        node.id
        for node in ast.walk(assigned_value)
        if isinstance(node, ast.Name)
    }

    referenced_strings = {
        node.value
        for node in ast.walk(assigned_value)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        )
    }

    assert "correction_metadata" not in referenced_names
    assert "detected_domain" not in referenced_strings
    assert "understanding" in referenced_names
    assert "direction_hints" in referenced_strings


def test_downstream_planning_layers_do_not_reparse_domain_from_raw_query():
    targets = (
        (
            "src/source_router.py",
            "retrieve_evidence",
        ),
        (
            "src/project_idea_generator.py",
            "generate_project_ideas",
        ),
        (
            "src/project_intelligence.py",
            "build_project_intelligence",
        ),
    )

    forbidden_calls = {
        "get_query_metadata",
        "extract_required_anchor_terms",
        "infer_domain_from_query",
        "detect_domain",
    }

    violations = []

    for relative_path, function_name in targets:
        tree = _module_tree(relative_path)
        function = _function_node(
            tree,
            function_name,
        )

        for forbidden_call in sorted(forbidden_calls):
            if _calls_named(
                function,
                forbidden_call,
            ):
                violations.append(
                    f"{relative_path}:{function_name}"
                    f" -> {forbidden_call}"
                )

    assert not violations, (
        "Downstream planning layers must consume the canonical "
        "planning domain rather than re-derive semantic intent "
        "from raw query text: "
        + "; ".join(violations)
    )


def test_project_intelligence_contains_no_raw_query_domain_authority():
    tree = _module_tree(
        "src/project_intelligence.py"
    )

    function_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    assert "infer_domain_from_query" not in function_names


def test_planning_domain_authority_flag_depends_only_on_resolved_domain():
    tree = _module_tree(
        "src/product_api.py"
    )

    handler = _function_node(
        tree,
        "generate_project_intelligence",
    )

    assignments = [
        node
        for node in ast.walk(handler)
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id
                == "has_authoritative_planning_domain"
                for target in node.targets
            )
        )
    ]

    assert len(assignments) == 1

    referenced_names = {
        node.id
        for node in ast.walk(assignments[0].value)
        if isinstance(node, ast.Name)
    }

    assert referenced_names == {
        "planning_domain",
    }, (
        "Planning-domain authority must come from the resolved "
        "planning_domain result, not be reconstructed from "
        "selected or canonical inputs."
    )
