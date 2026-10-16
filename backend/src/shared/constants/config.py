from pathlib import Path

ENV_PREFIX = "APP_"
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_FILE = BACKEND_ROOT / "config" / "models.toml"
