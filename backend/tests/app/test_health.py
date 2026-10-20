from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.app.main import create_app
from src.shared.config.settings import load_settings
from src.shared.constants.config import DEFAULT_CONFIG_FILE
from src.shared.enums.health_status import HealthStatus


def test_health_reports_ok(tmp_path: Path):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    app = create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 18, tzinfo=UTC))
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": HealthStatus.OK.value}
    assert HealthStatus.OK.value == "ok"
