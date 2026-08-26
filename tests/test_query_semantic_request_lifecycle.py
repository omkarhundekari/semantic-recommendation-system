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
