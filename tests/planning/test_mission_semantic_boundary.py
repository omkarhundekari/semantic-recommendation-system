import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MISSION_FILES = (
    ROOT / "src/planning/mission_context.py",
    ROOT / "src/planning/guided_step_generator.py",
    ROOT / "src/planning/mission_specificity_validator.py",
    ROOT / "src/planning/roadmap_execution_enrichment.py",
)

FORBIDDEN_SEMANTIC_MODULES = {
    "query_expander",
    "research_query_anchors",
    "planning.query_anchor_direction_adapter",
}

FORBIDDEN_MISSION_CONTEXT_NAMES = {
    "KNOWN_STACK_TERMS",
    "DOMAIN_STACK_TERMS",
    "_extract_stack_terms",
    "_contains_stack_term",
    "_filter_stack_for_domain",
    "extract_query_anchors",
}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(), filename=str(path))


def _imported_modules(tree: ast.AST) -> set[str]:
    modules = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)

    return modules


def test_mission_layer_does_not_import_legacy_semantic_parsers():
    violations = []

    for path in MISSION_FILES:
        imported = _imported_modules(_tree(path))
        forbidden = sorted(imported & FORBIDDEN_SEMANTIC_MODULES)

        if forbidden:
            violations.append(
                f"{path.name}: {', '.join(forbidden)}"
            )

    assert not violations, (
        "Mission planning must consume canonical typed semantics "
        "instead of importing legacy semantic parsers: "
        + "; ".join(violations)
    )


def test_mission_context_contains_no_legacy_stack_or_anchor_authority():
    path = ROOT / "src/planning/mission_context.py"
    tree = _tree(path)

    referenced = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    }

    remaining = sorted(
        referenced & FORBIDDEN_MISSION_CONTEXT_NAMES
    )

    assert not remaining, (
        "Legacy mission semantic authority remains: "
        + ", ".join(remaining)
    )


def test_build_mission_context_does_not_accept_raw_query():
    path = ROOT / "src/planning/mission_context.py"
    tree = _tree(path)

    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_mission_context"
    )

    parameters = {
        arg.arg
        for arg in (
            list(function.args.posonlyargs)
            + list(function.args.args)
            + list(function.args.kwonlyargs)
        )
    }

    assert "query" not in parameters, (
        "build_mission_context must not accept raw query text once "
        "canonical planning semantics are required."
    )


def test_planning_semantics_is_required():
    path = ROOT / "src/planning/mission_context.py"
    tree = _tree(path)

    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_mission_context"
    )

    positional = list(function.args.args)
    positional_defaults = list(function.args.defaults)

    positional_default_names = {
        arg.arg
        for arg in positional[
            len(positional) - len(positional_defaults):
        ]
    }

    kw_defaults = {
        arg.arg: default
        for arg, default in zip(
            function.args.kwonlyargs,
            function.args.kw_defaults,
        )
    }

    all_names = {
        arg.arg
        for arg in (
            list(function.args.posonlyargs)
            + positional
            + list(function.args.kwonlyargs)
        )
    }

    assert "planning_semantics" in all_names

    if "planning_semantics" in positional_default_names:
        raise AssertionError(
            "planning_semantics must not have a default."
        )

    if (
        "planning_semantics" in kw_defaults
        and kw_defaults["planning_semantics"] is not None
    ):
        raise AssertionError(
            "planning_semantics must be required."
        )


def test_mission_context_does_not_semantically_parse_user_goal():
    path = ROOT / "src/planning/mission_context.py"
    tree = _tree(path)

    forbidden_calls = {
        "extract_query_anchors",
        "_extract_stack_terms",
        "detect_domain",
        "get_query_metadata",
    }

    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        else:
            continue

        if call_name not in forbidden_calls:
            continue

        for arg in node.args:
            if any(
                isinstance(child, ast.Name)
                and child.id == "user_goal"
                for child in ast.walk(arg)
            ):
                violations.append(call_name)

    assert not violations, (
        "user_goal must remain presentation/context data, not a "
        "semantic-parser input: "
        + ", ".join(sorted(set(violations)))
    )
