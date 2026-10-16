import ast
import io
import tokenize
from dataclasses import dataclass

TOOL_DIRECTIVE_PREFIXES = ("# noqa", "# type:", "# ruff:", "# pragma", "# fmt:")
GENERIC_EXCEPTIONS = {"Exception", "BaseException", "RuntimeError", "ValueError", "TypeError", "KeyError", "AssertionError"}
TERMINAL_STATEMENTS = (ast.Return, ast.Raise, ast.Continue, ast.Break)
CONTROL_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try)
FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)
DOCSTRING_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
MAX_NESTING = 2
MAX_FUNCTION_LINES = 60
MAX_BRANCHES = 8


@dataclass(frozen=True)
class Violation:
    rule: str
    line: int


def find_violations(source: str) -> list[Violation]:
    tree = ast.parse(source)
    violations = [*find_comments(source), *find_docstrings(tree)]
    for node in ast.walk(tree):
        violations.extend(check_node(node))
    return violations


def find_comments(source: str) -> list[Violation]:
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return [
        Violation("no-comments", token.start[0])
        for token in tokens
        if token.type == tokenize.COMMENT and not token.string.startswith(TOOL_DIRECTIVE_PREFIXES)
    ]


def find_docstrings(tree: ast.AST) -> list[Violation]:
    return [
        Violation("no-docstrings", node.lineno if hasattr(node, "lineno") else 1)
        for node in ast.walk(tree)
        if isinstance(node, DOCSTRING_OWNERS) and ast.get_docstring(node) is not None
    ]


def check_node(node: ast.AST) -> list[Violation]:
    checks = (
        check_env_read,
        check_generic_exception,
        check_relative_import,
        check_else_after_terminal,
        check_magic_string_compare,
        check_function_shape,
    )
    return [violation for check in checks for violation in check(node)]


def check_env_read(node: ast.AST) -> list[Violation]:
    if not isinstance(node, ast.Attribute):
        return []
    is_os = isinstance(node.value, ast.Name) and node.value.id == "os"
    if is_os and node.attr in {"environ", "getenv"}:
        return [Violation("no-env-read", node.lineno)]
    return []


def check_generic_exception(node: ast.AST) -> list[Violation]:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return []
    raised = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
    if isinstance(raised, ast.Name) and raised.id in GENERIC_EXCEPTIONS:
        return [Violation("no-generic-exception", node.lineno)]
    return []


def check_relative_import(node: ast.AST) -> list[Violation]:
    if isinstance(node, ast.ImportFrom) and node.level > 0:
        return [Violation("no-relative-import", node.lineno)]
    return []


def check_else_after_terminal(node: ast.AST) -> list[Violation]:
    if not isinstance(node, ast.If) or not node.orelse:
        return []
    if isinstance(node.body[-1], TERMINAL_STATEMENTS):
        return [Violation("no-else-after-terminal", node.lineno)]
    return []


def check_magic_string_compare(node: ast.AST) -> list[Violation]:
    if not isinstance(node, ast.Compare):
        return []
    has_equality = any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.ops)
    operands = [node.left, *node.comparators]
    has_string = any(isinstance(operand, ast.Constant) and isinstance(operand.value, str) for operand in operands)
    if has_equality and has_string:
        return [Violation("no-magic-string-compare", node.lineno)]
    return []


def check_function_shape(node: ast.AST) -> list[Violation]:
    if not isinstance(node, FUNCTION_NODES):
        return []
    violations = []
    if node.end_lineno - node.lineno + 1 > MAX_FUNCTION_LINES:
        violations.append(Violation("max-function-lines", node.lineno))
    if count_branches(node) > MAX_BRANCHES:
        violations.append(Violation("max-branches", node.lineno))
    if max_nesting(node) > MAX_NESTING:
        violations.append(Violation("max-nesting", node.lineno))
    return violations


def count_branches(function: ast.AST) -> int:
    branch_nodes = (*CONTROL_NODES, ast.ExceptHandler, ast.match_case)
    return sum(isinstance(child, branch_nodes) for child in walk_own_body(function))


def walk_own_body(function: ast.AST):
    pending = list(ast.iter_child_nodes(function))
    while pending:
        node = pending.pop()
        if isinstance(node, FUNCTION_NODES):
            continue
        yield node
        pending.extend(ast.iter_child_nodes(node))


def max_nesting(function: ast.AST) -> int:
    return deepest_control(function, depth=0, is_elif=False)


def deepest_control(node: ast.AST, depth: int, is_elif: bool) -> int:
    deepest = depth
    for field, value in ast.iter_fields(node):
        for child in value if isinstance(value, list) else [value]:
            if isinstance(child, FUNCTION_NODES) and child is not node:
                continue
            if not isinstance(child, ast.AST):
                continue
            child_is_elif = isinstance(node, ast.If) and field == "orelse" and isinstance(child, ast.If) and len(value) == 1
            increases = isinstance(child, CONTROL_NODES) and not child_is_elif
            deepest = max(deepest, deepest_control(child, depth + int(increases), child_is_elif))
    return deepest
