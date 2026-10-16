from pathlib import Path

import pytest

from src.shared.config.settings import load_settings
from src.shared.constants.config import BACKEND_ROOT
from src.shared.errors.invalid_configuration_error import InvalidConfigurationError

VALID_CONFIG = """
active_profile = "small"

[ollama]
base_url = "http://127.0.0.1:11434"
timeout_seconds = 600

[prompts]
system_file = "config/prompts/analyst_system.md"
notes_file = "config/prompts/notes_system.md"
summary_file = "config/prompts/summary_system.md"

[storage]
notes_dir = "data/notes"

[profiles.small]
model = "qwen2.5:3b"
num_ctx = 8192
temperature = 0.2
top_p = 0.9
keep_alive = "30m"
chunk_size_chars = 6000
chunk_overlap_chars = 400
max_output_tokens = 1024

[profiles.large]
model = "qwen2.5:7b"
num_ctx = 8192
temperature = 0.2
top_p = 0.9
keep_alive = "30m"
chunk_size_chars = 6000
chunk_overlap_chars = 400
max_output_tokens = 1024
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG, encoding="utf-8")
    return path


def test_loads_active_profile_from_file(config_file: Path):
    settings = load_settings(config_file)
    assert settings.active_profile == "small"
    assert settings.active.model == "qwen2.5:3b"
    assert settings.ollama.base_url == "http://127.0.0.1:11434"


def test_environment_variable_overrides_active_profile(config_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ACTIVE_PROFILE", "large")
    settings = load_settings(config_file)
    assert settings.active.model == "qwen2.5:7b"


def test_unknown_profile_fails_at_startup(config_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ACTIVE_PROFILE", "huge")
    with pytest.raises(InvalidConfigurationError) as raised:
        load_settings(config_file)
    assert raised.value.profile == "huge"


def test_missing_file_fails_at_startup(tmp_path: Path):
    with pytest.raises(InvalidConfigurationError):
        load_settings(tmp_path / "missing.toml")


def test_invalid_value_fails_at_startup(tmp_path: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("num_ctx = 8192", "num_ctx = 0", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path)


def test_overlap_not_smaller_than_chunk_fails_at_startup(tmp_path: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("chunk_overlap_chars = 400", "chunk_overlap_chars = 6000", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path)


def test_system_prompt_path_is_resolved_from_backend_root(config_file: Path):
    settings = load_settings(config_file)
    assert settings.system_prompt_path == BACKEND_ROOT / "config/prompts/analyst_system.md"


def test_notes_and_summary_prompt_paths_are_resolved_from_backend_root(config_file: Path):
    settings = load_settings(config_file)
    assert settings.notes_prompt_path == BACKEND_ROOT / "config/prompts/notes_system.md"
    assert settings.summary_prompt_path == BACKEND_ROOT / "config/prompts/summary_system.md"


def test_notes_directory_is_resolved_from_backend_root(config_file: Path):
    assert load_settings(config_file).notes_dir_path == BACKEND_ROOT / "data/notes"


def test_missing_storage_section_fails_at_startup(tmp_path: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace('[storage]\nnotes_dir = "data/notes"\n', ""), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path)


def test_summary_profile_defaults_to_the_active_profile(config_file: Path):
    settings = load_settings(config_file)
    assert settings.summary.model == "qwen2.5:3b"


def test_summary_profile_can_differ_from_the_active_one(tmp_path: Path):
    path = tmp_path / "models.toml"
    path.write_text(
        VALID_CONFIG.replace('active_profile = "small"', 'active_profile = "small"\nsummary_profile = "large"'), encoding="utf-8"
    )
    settings = load_settings(path)
    assert settings.active.model == "qwen2.5:3b"
    assert settings.summary.model == "qwen2.5:7b"


def test_environment_variable_overrides_summary_profile(config_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_SUMMARY_PROFILE", "large")
    assert load_settings(config_file).summary.model == "qwen2.5:7b"


def test_unknown_summary_profile_fails_at_startup(tmp_path: Path):
    path = tmp_path / "models.toml"
    path.write_text(
        VALID_CONFIG.replace('active_profile = "small"', 'active_profile = "small"\nsummary_profile = "huge"'), encoding="utf-8"
    )
    with pytest.raises(InvalidConfigurationError) as raised:
        load_settings(path)
    assert raised.value.profile == "huge"
