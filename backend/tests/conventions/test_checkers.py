from tests.conventions.checkers import find_violations


def rules_in(source: str) -> set[str]:
    return {violation.rule for violation in find_violations(source)}


def test_flags_comment():
    assert "no-comments" in rules_in("x = 1  # explanation\n")


def test_allows_tool_directive_comment():
    assert "no-comments" not in rules_in("x = 1  # noqa: E501\n")


def test_flags_docstring():
    assert "no-docstrings" in rules_in('def f():\n    """text"""\n    return 1\n')


def test_flags_environment_read():
    assert "no-env-read" in rules_in("import os\nx = os.environ['A']\n")
    assert "no-env-read" in rules_in("import os\nx = os.getenv('A')\n")


def test_flags_generic_exception():
    assert "no-generic-exception" in rules_in("def f():\n    raise ValueError('x')\n")
    assert "no-generic-exception" in rules_in("def f():\n    raise Exception\n")


def test_flags_relative_import():
    assert "no-relative-import" in rules_in("from .a import b\n")


def test_flags_else_after_return():
    source = "def f(a):\n    if a:\n        return 1\n    else:\n        return 2\n"
    assert "no-else-after-terminal" in rules_in(source)


def test_flags_nesting_deeper_than_two():
    source = "def f(a, b, c):\n    if a:\n        if b:\n            if c:\n                return 1\n    return 0\n"
    assert "max-nesting" in rules_in(source)


def test_elif_chain_is_not_nesting():
    source = "def f(a):\n    if a == 1:\n        x = 1\n    elif a == 2:\n        x = 2\n    elif a == 3:\n        x = 3\n    else:\n        x = 4\n    return x\n"
    assert "max-nesting" not in rules_in(source)


def test_flags_function_longer_than_sixty_lines():
    body = "".join(f"    x{i} = {i}\n" for i in range(61))
    assert "max-function-lines" in rules_in(f"def f():\n{body}    return 0\n")


def test_flags_more_than_eight_branches():
    body = "".join(f"    if a == {i}:\n        x = {i}\n" for i in range(9))
    assert "max-branches" in rules_in(f"def f(a):\n    x = 0\n{body}    return x\n")


def test_flags_string_literal_comparison():
    assert "no-magic-string-compare" in rules_in("def f(a):\n    return a == 'active'\n")


def test_clean_code_has_no_violations():
    source = "def f(a):\n    if not a:\n        return 0\n    return a + 1\n"
    assert find_violations(source) == []
