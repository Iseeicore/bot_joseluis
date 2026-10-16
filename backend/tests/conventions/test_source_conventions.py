from pathlib import Path

import pytest

from tests.conventions.checkers import find_violations

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
SOURCE_FILES = sorted(path for path in SOURCE_ROOT.rglob("*.py") if path.stat().st_size > 0)


@pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: str(path.relative_to(SOURCE_ROOT)))
def test_source_file_follows_conventions(path: Path):
    violations = find_violations(path.read_text(encoding="utf-8"))
    assert violations == [], [f"{path.name}:{v.line} {v.rule}" for v in violations]
