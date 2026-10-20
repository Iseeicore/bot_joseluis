from fastapi import FastAPI

from src.app.database_lifespan import Lifespan, run_jobs_on_startup
from src.app.error_handlers import register_error_handlers
from src.app.health_router import router as health_router
from src.app.job_composition import build_job_runtime
from src.document_analysis.api.job_dependencies import JobUseCases
from src.document_analysis.api.jobs_router import router as jobs_router
from src.shared.config.settings import Settings, load_settings
from src.shared.config.system_prompt import load_prompt_file
from src.shared.constants.config import MIGRATIONS_DIR
from src.shared.types.clock import Clock
from src.shared.utils.utc_now import utc_now


def create_app(
    settings: Settings,
    system_prompt: str,
    now: Clock,
    lifespan: Lifespan | None = None,
    job_use_cases: JobUseCases | None = None,
) -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.state.system_prompt = system_prompt
    register_error_handlers(app, now)
    app.include_router(health_router)
    if job_use_cases is not None:
        app.state.job_use_cases = job_use_cases
        app.include_router(jobs_router)
    return app


def build_default_app() -> FastAPI:
    settings = load_settings()
    runtime = build_job_runtime(settings, utc_now)
    lifespan = run_jobs_on_startup(settings.database_file_path, MIGRATIONS_DIR, runtime.recover, runtime.worker)
    return create_app(settings, load_prompt_file(settings.system_prompt_path), utc_now, lifespan, runtime.use_cases)
