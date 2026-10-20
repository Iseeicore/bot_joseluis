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
database_file = "data/app.db"
uploads_dir = "data/uploads"

[profiles.small]
model = "qwen2.5:3b"
num_ctx = 8192
temperature = 0.2
top_p = 0.9
keep_alive = "30m"
chunk_size_chars = 6000
chunk_overlap_chars = 400
summary_batch_chars = 15000
max_output_tokens = 1024
think = false

[profiles.large]
model = "qwen2.5:7b"
num_ctx = 8192
temperature = 0.2
top_p = 0.9
keep_alive = "30m"
chunk_size_chars = 6000
chunk_overlap_chars = 400
summary_batch_chars = 15000
max_output_tokens = 1024
think = false
"""


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG, encoding="utf-8")
    return path


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    return tmp_path / ".env"


def test_loads_active_profile_from_file(config_file: Path, env_file: Path):
    settings = load_settings(config_file, env_file)
    assert settings.active_profile == "small"
    assert settings.active.model == "qwen2.5:3b"
    assert settings.ollama.base_url == "http://127.0.0.1:11434"


def test_environment_variable_overrides_active_profile(config_file: Path, monkeypatch: pytest.MonkeyPatch, env_file: Path):
    monkeypatch.setenv("APP_ACTIVE_PROFILE", "large")
    settings = load_settings(config_file, env_file)
    assert settings.active.model == "qwen2.5:7b"


def test_unknown_profile_fails_at_startup(config_file: Path, monkeypatch: pytest.MonkeyPatch, env_file: Path):
    monkeypatch.setenv("APP_ACTIVE_PROFILE", "huge")
    with pytest.raises(InvalidConfigurationError) as raised:
        load_settings(config_file, env_file)
    assert raised.value.profile == "huge"


def test_missing_file_fails_at_startup(tmp_path: Path):
    with pytest.raises(InvalidConfigurationError):
        load_settings(tmp_path / "missing.toml", tmp_path / ".env")


def test_invalid_value_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("num_ctx = 8192", "num_ctx = 0", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_overlap_not_smaller_than_chunk_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("chunk_overlap_chars = 400", "chunk_overlap_chars = 6000", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_system_prompt_path_is_resolved_from_backend_root(config_file: Path, env_file: Path):
    settings = load_settings(config_file, env_file)
    assert settings.system_prompt_path == BACKEND_ROOT / "config/prompts/analyst_system.md"


def test_notes_and_summary_prompt_paths_are_resolved_from_backend_root(config_file: Path, env_file: Path):
    settings = load_settings(config_file, env_file)
    assert settings.notes_prompt_path == BACKEND_ROOT / "config/prompts/notes_system.md"
    assert settings.summary_prompt_path == BACKEND_ROOT / "config/prompts/summary_system.md"


def test_notes_directory_is_resolved_from_backend_root(config_file: Path, env_file: Path):
    assert load_settings(config_file, env_file).notes_dir_path == BACKEND_ROOT / "data/notes"


def test_missing_storage_section_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(
        VALID_CONFIG.replace('[storage]\nnotes_dir = "data/notes"\ndatabase_file = "data/app.db"\nuploads_dir = "data/uploads"\n', ""),
        encoding="utf-8",
    )
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_summary_profile_defaults_to_the_active_profile(config_file: Path, env_file: Path):
    settings = load_settings(config_file, env_file)
    assert settings.summary.model == "qwen2.5:3b"


def test_summary_profile_can_differ_from_the_active_one(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(
        VALID_CONFIG.replace('active_profile = "small"', 'active_profile = "small"\nsummary_profile = "large"'), encoding="utf-8"
    )
    settings = load_settings(path, env_file)
    assert settings.active.model == "qwen2.5:3b"
    assert settings.summary.model == "qwen2.5:7b"


def test_environment_variable_overrides_summary_profile(config_file: Path, monkeypatch: pytest.MonkeyPatch, env_file: Path):
    monkeypatch.setenv("APP_SUMMARY_PROFILE", "large")
    assert load_settings(config_file, env_file).summary.model == "qwen2.5:7b"


def test_unknown_summary_profile_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(
        VALID_CONFIG.replace('active_profile = "small"', 'active_profile = "small"\nsummary_profile = "huge"'), encoding="utf-8"
    )
    with pytest.raises(InvalidConfigurationError) as raised:
        load_settings(path, env_file)
    assert raised.value.profile == "huge"


def test_profile_think_mode_is_loaded_from_file(config_file: Path, env_file: Path):
    assert load_settings(config_file, env_file).active.think is False


def test_profile_without_think_mode_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("think = false\n", "", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_database_file_is_resolved_from_backend_root(config_file: Path, env_file: Path):
    assert load_settings(config_file, env_file).database_file_path == BACKEND_ROOT / "data/app.db"


def test_uploads_directory_is_resolved_from_backend_root(config_file: Path, env_file: Path):
    assert load_settings(config_file, env_file).uploads_dir_path == BACKEND_ROOT / "data/uploads"


def test_missing_uploads_directory_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace('uploads_dir = "data/uploads"\n', ""), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_nested_environment_variable_overrides_only_its_field(config_file: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_OLLAMA__BASE_URL", "http://ollama:11434")
    settings = load_settings(config_file, env_file)
    assert settings.ollama.base_url == "http://ollama:11434"
    assert settings.ollama.timeout_seconds == 600


def test_nested_environment_variable_reaches_a_profile_field(config_file: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_PROFILES__SMALL__THINK", "true")
    settings = load_settings(config_file, env_file)
    assert settings.active.think is True
    assert settings.active.model == "qwen2.5:3b"


def test_dotenv_file_overrides_the_toml_file(config_file: Path, env_file: Path):
    env_file.write_text("APP_ACTIVE_PROFILE=large\nAPP_STORAGE__DATABASE_FILE=data/other.db\n", encoding="utf-8")
    settings = load_settings(config_file, env_file)
    assert settings.active.model == "qwen2.5:7b"
    assert settings.database_file_path == BACKEND_ROOT / "data/other.db"
    assert settings.storage.notes_dir == Path("data/notes")


def test_environment_variable_overrides_the_dotenv_file(config_file: Path, env_file: Path, monkeypatch: pytest.MonkeyPatch):
    env_file.write_text("APP_OLLAMA__BASE_URL=http://from-dotenv:11434\n", encoding="utf-8")
    monkeypatch.setenv("APP_OLLAMA__BASE_URL", "http://from-env:11434")
    assert load_settings(config_file, env_file).ollama.base_url == "http://from-env:11434"


def test_unknown_variable_in_dotenv_file_fails_at_startup(config_file: Path, env_file: Path):
    env_file.write_text("APP_ACTIVE_PROFIL=large\n", encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(config_file, env_file)


def test_missing_dotenv_file_falls_back_to_the_toml_file(config_file: Path, env_file: Path):
    assert not env_file.exists()
    assert load_settings(config_file, env_file).ollama.base_url == "http://127.0.0.1:11434"


def test_profile_summary_batch_size_is_loaded_from_file(config_file: Path, env_file: Path):
    assert load_settings(config_file, env_file).active.summary_batch_chars == 15000


def test_profile_without_summary_batch_size_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("summary_batch_chars = 15000\n", "", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError):
        load_settings(path, env_file)


def test_summary_batch_that_fills_the_context_estimate_loads(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("summary_batch_chars = 15000", "summary_batch_chars = 21504", 1), encoding="utf-8")
    assert load_settings(path, env_file).active.summary_batch_chars == 21504


def test_summary_batch_larger_than_the_context_estimate_fails_at_startup(tmp_path: Path, env_file: Path):
    path = tmp_path / "models.toml"
    path.write_text(VALID_CONFIG.replace("summary_batch_chars = 15000", "summary_batch_chars = 21505", 1), encoding="utf-8")
    with pytest.raises(InvalidConfigurationError) as raised:
        load_settings(path, env_file)
    assert "summary_batch_chars (21505)" in raised.value.reason
