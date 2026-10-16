from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.app.main import build_default_app, create_app
from src.shared.config.settings import load_settings
from src.shared.constants.config import DEFAULT_CONFIG_FILE


def test_app_keeps_settings_and_formats_unknown_route():
    settings = load_settings(DEFAULT_CONFIG_FILE)
    app = create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 16, tzinfo=UTC))
    response = TestClient(app).get("/nope")
    assert app.state.settings is settings
    assert response.status_code == 404
    assert response.json()["errorCode"] == "NOT_FOUND"


def test_default_config_file_exists_and_loads():
    assert Path(DEFAULT_CONFIG_FILE).is_file()
    assert load_settings().active.model == "qwen2.5:3b"


def test_default_app_loads_the_real_system_prompt():
    app = build_default_app()
    assert app.state.system_prompt
    assert "No consta en el documento" in app.state.system_prompt


def test_default_config_points_to_existing_nonempty_prompts():
    settings = load_settings()
    assert settings.notes_prompt_path.read_text(encoding="utf-8").strip()
    assert settings.summary_prompt_path.read_text(encoding="utf-8").strip()
