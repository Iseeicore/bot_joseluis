from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, TomlConfigSettingsSource

from src.shared.constants.config import (
    BACKEND_ROOT,
    DEFAULT_CONFIG_FILE,
    DEFAULT_ENV_FILE,
    ENV_FILE_ENCODING,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
)
from src.shared.constants.limits.model_context import CONSERVATIVE_CHARS_PER_TOKEN
from src.shared.constants.texts.configuration import (
    invalid_config_text,
    missing_config_file_text,
    unknown_profile_text,
)
from src.shared.errors.invalid_chunk_overlap_error import InvalidChunkOverlapError
from src.shared.errors.invalid_configuration_error import InvalidConfigurationError
from src.shared.errors.summary_batch_too_large_error import SummaryBatchTooLargeError


class OllamaSettings(BaseModel):
    base_url: str
    timeout_seconds: int = Field(gt=0)


class PromptSettings(BaseModel):
    system_file: Path
    notes_file: Path
    summary_file: Path


class StorageSettings(BaseModel):
    notes_dir: Path
    database_file: Path
    uploads_dir: Path


class ModelProfile(BaseModel):
    model: str
    num_ctx: int = Field(gt=0)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    keep_alive: str
    chunk_size_chars: int = Field(gt=0)
    chunk_overlap_chars: int = Field(ge=0)
    summary_batch_chars: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    think: bool

    @model_validator(mode="after")
    def ensure_overlap_is_smaller_than_chunk(self) -> "ModelProfile":
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise InvalidChunkOverlapError(self.chunk_overlap_chars, self.chunk_size_chars)
        return self

    @model_validator(mode="after")
    def ensure_summary_batch_fits_the_context(self) -> "ModelProfile":
        limit = (self.num_ctx - self.max_output_tokens) * CONSERVATIVE_CHARS_PER_TOKEN
        if self.summary_batch_chars > limit:
            raise SummaryBatchTooLargeError(self.summary_batch_chars, limit)
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, env_nested_delimiter=ENV_NESTED_DELIMITER)

    active_profile: str
    summary_profile: str | None = None
    ollama: OllamaSettings
    prompts: PromptSettings
    storage: StorageSettings
    profiles: dict[str, ModelProfile]

    @model_validator(mode="after")
    def ensure_profiles_exist(self) -> "Settings":
        for name in (self.active_profile, self.summary_profile):
            if name is not None and name not in self.profiles:
                raise InvalidConfigurationError(reason=unknown_profile_text(name, list(self.profiles)), profile=name)
        return self

    @property
    def system_prompt_path(self) -> Path:
        return BACKEND_ROOT / self.prompts.system_file

    @property
    def notes_prompt_path(self) -> Path:
        return BACKEND_ROOT / self.prompts.notes_file

    @property
    def summary_prompt_path(self) -> Path:
        return BACKEND_ROOT / self.prompts.summary_file

    @property
    def notes_dir_path(self) -> Path:
        return BACKEND_ROOT / self.storage.notes_dir

    @property
    def database_file_path(self) -> Path:
        return BACKEND_ROOT / self.storage.database_file

    @property
    def uploads_dir_path(self) -> Path:
        return BACKEND_ROOT / self.storage.uploads_dir

    @property
    def active(self) -> ModelProfile:
        return self.profiles[self.active_profile]

    @property
    def summary(self) -> ModelProfile:
        return self.profiles[self.summary_profile or self.active_profile]


def settings_class_for(config_file: Path, env_file: Path) -> type[Settings]:
    class FileSettings(Settings):
        model_config = SettingsConfigDict(
            env_prefix=ENV_PREFIX,
            env_nested_delimiter=ENV_NESTED_DELIMITER,
            env_file=env_file,
            env_file_encoding=ENV_FILE_ENCODING,
            toml_file=config_file,
        )

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (init_settings, env_settings, dotenv_settings, TomlConfigSettingsSource(settings_cls))

    return FileSettings


def load_settings(config_file: Path = DEFAULT_CONFIG_FILE, env_file: Path = DEFAULT_ENV_FILE) -> Settings:
    if not config_file.is_file():
        raise InvalidConfigurationError(reason=missing_config_file_text(config_file))
    try:
        return settings_class_for(config_file, env_file)()
    except ValidationError as error:
        raise InvalidConfigurationError(reason=invalid_config_text(str(error))) from error
