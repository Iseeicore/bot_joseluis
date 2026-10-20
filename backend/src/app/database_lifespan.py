from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, closing
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI

from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.document_analysis.infrastructure.persistence.sqlite_migrations import apply_migrations

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class BackgroundWorker(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...


def migrate(database_file: Path, migrations_dir: Path) -> None:
    with closing(open_database(database_file)) as connection:
        apply_migrations(connection, migrations_dir)


def migrate_on_startup(database_file: Path, migrations_dir: Path) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        migrate(database_file, migrations_dir)
        yield

    return lifespan


def run_jobs_on_startup(database_file: Path, migrations_dir: Path, recover: Callable[[], int], worker: BackgroundWorker) -> Lifespan:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        migrate(database_file, migrations_dir)
        recover()
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    return lifespan
