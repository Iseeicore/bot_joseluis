from src.shared.config.settings import Settings
from src.shared.constants.config import BACKEND_ROOT, ENV_PREFIX


def test_env_example_lists_every_scalar_setting():
    example = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")
    scalar_names = [name for name, field in Settings.model_fields.items() if field.annotation is str]
    assert scalar_names
    for name in scalar_names:
        assert f"{ENV_PREFIX}{name.upper()}=" in example
