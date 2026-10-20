from pathlib import Path

ENV_PREFIX = "APP_"
ENV_NESTED_DELIMITER = "__"
ENV_FILE_ENCODING = "utf-8"
BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_FILE = BACKEND_ROOT / "config" / "models.toml"
DEFAULT_ENV_FILE = BACKEND_ROOT / ".env"
MIGRATIONS_DIR = BACKEND_ROOT / "migrations"
