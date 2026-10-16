from pathlib import Path

from src.shared.constants.texts.configuration import empty_prompt_file_text, missing_prompt_file_text
from src.shared.errors.invalid_configuration_error import InvalidConfigurationError


def load_prompt_file(prompt_file: Path) -> str:
    if not prompt_file.is_file():
        raise InvalidConfigurationError(reason=missing_prompt_file_text(prompt_file))
    content = prompt_file.read_text(encoding="utf-8").strip()
    if not content:
        raise InvalidConfigurationError(reason=empty_prompt_file_text(prompt_file))
    return content
