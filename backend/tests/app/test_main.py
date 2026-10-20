from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.app.main import build_default_app, create_app
from src.shared.config.settings import load_settings
from src.shared.constants.config import BACKEND_ROOT, DEFAULT_CONFIG_FILE


def test_app_keeps_settings_and_formats_unknown_route():
    settings = load_settings(DEFAULT_CONFIG_FILE)
    app = create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 16, tzinfo=UTC))
    response = TestClient(app).get("/nope")
    assert app.state.settings is settings
    assert response.status_code == 404
    assert response.json()["errorCode"] == "NOT_FOUND"


def test_default_config_file_exists_and_loads(tmp_path: Path):
    assert Path(DEFAULT_CONFIG_FILE).is_file()
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    assert settings.active.model == "qwen3.5:4b"
    assert settings.summary.model == "qwen3.5:9b"
    assert settings.active.think is False
    assert settings.summary.think is False
    assert settings.active.summary_batch_chars == 15000
    assert settings.summary.summary_batch_chars == 13000
    assert settings.active.max_output_tokens == 1024
    assert settings.summary.max_output_tokens == 2048
    assert settings.database_file_path == BACKEND_ROOT / "data/app.db"
    assert settings.uploads_dir_path == BACKEND_ROOT / "data/uploads"


def test_default_app_loads_the_real_system_prompt():
    app = build_default_app()
    assert app.state.system_prompt
    assert "No consta en el documento" in app.state.system_prompt


def test_default_config_points_to_existing_nonempty_prompts():
    settings = load_settings()
    assert settings.notes_prompt_path.read_text(encoding="utf-8").strip()
    assert settings.summary_prompt_path.read_text(encoding="utf-8").strip()


def test_default_app_exposes_the_job_endpoints():
    app = build_default_app()
    assert {"/jobs", "/jobs/{job_id}", "/health"} <= set(app.openapi()["paths"])


def test_app_without_job_use_cases_has_no_job_endpoints(tmp_path: Path):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    app = create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 16, tzinfo=UTC))
    assert set(app.openapi()["paths"]) == {"/health"}
