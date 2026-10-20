from pydantic import BaseModel

from src.shared.config.settings import Settings, load_settings
from src.shared.constants.config import BACKEND_ROOT, DEFAULT_CONFIG_FILE, ENV_NESTED_DELIMITER, ENV_PREFIX

ENV_EXAMPLE = BACKEND_ROOT / ".env.example"
SCALAR_ANNOTATIONS = (str, str | None)
DEPLOY_OVERRIDES = ("APP_OLLAMA__BASE_URL", "APP_STORAGE__DATABASE_FILE")


def example_names() -> list[str]:
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    return [line.split("=", 1)[0] for line in lines if line.strip()]


def targets_a_setting(name: str) -> bool:
    model: object = Settings
    for part in name.removeprefix(ENV_PREFIX).lower().split(ENV_NESTED_DELIMITER):
        if not (isinstance(model, type) and issubclass(model, BaseModel)) or part not in model.model_fields:
            return False
        model = model.model_fields[part].annotation
    return True


def test_env_example_lists_every_scalar_setting():
    scalar_names = [name for name, field in Settings.model_fields.items() if field.annotation in SCALAR_ANNOTATIONS]
    assert scalar_names
    for name in scalar_names:
        assert f"{ENV_PREFIX}{name.upper()}" in example_names()


def test_env_example_lists_the_nested_overrides_used_by_the_deploy():
    for name in DEPLOY_OVERRIDES:
        assert name in example_names()


def test_every_env_example_variable_targets_a_real_setting():
    names = example_names()
    assert names
    assert [name for name in names if not targets_a_setting(name)] == []


def test_env_example_loads_on_top_of_the_default_config():
    settings = load_settings(DEFAULT_CONFIG_FILE, ENV_EXAMPLE)
    assert settings.active_profile in settings.profiles
    assert settings.summary_profile in settings.profiles
