from fastapi import FastAPI

from src.app.error_handlers import Clock, register_error_handlers
from src.shared.config.settings import Settings, load_settings
from src.shared.config.system_prompt import load_prompt_file
from src.shared.utils.utc_now import utc_now


def create_app(settings: Settings, system_prompt: str, now: Clock) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings
    app.state.system_prompt = system_prompt
    register_error_handlers(app, now)
    return app


def build_default_app() -> FastAPI:
    settings = load_settings()
    return create_app(settings, load_prompt_file(settings.system_prompt_path), utc_now)
