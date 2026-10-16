from pathlib import Path

import pytest

from src.shared.config.system_prompt import load_prompt_file
from src.shared.errors.invalid_configuration_error import InvalidConfigurationError


def test_returns_file_content(tmp_path: Path):
    path = tmp_path / "prompt.md"
    path.write_text("reglas\n", encoding="utf-8")
    assert load_prompt_file(path) == "reglas"


def test_missing_file_fails_at_startup(tmp_path: Path):
    with pytest.raises(InvalidConfigurationError):
        load_prompt_file(tmp_path / "missing.md")


def test_blank_file_fails_at_startup(tmp_path: Path):
    path = tmp_path / "prompt.md"
    path.write_text("  \n\n", encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_prompt_file(path)
