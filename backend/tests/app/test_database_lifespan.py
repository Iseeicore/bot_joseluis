import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app.database_lifespan import migrate_on_startup, run_jobs_on_startup
from src.app.main import build_default_app, create_app
from src.document_analysis.application.recover_interrupted_jobs import recover_interrupted_jobs
from src.document_analysis.domain.models import NewDocumentVersion, NewJob
from src.document_analysis.infrastructure.persistence.sqlite_database import open_database
from src.document_analysis.infrastructure.persistence.sqlite_job_repository import open_job_transaction
from src.document_analysis.infrastructure.persistence.sqlite_migrations import apply_migrations
from src.shared.config.settings import load_settings
from src.shared.constants.config import DEFAULT_CONFIG_FILE, MIGRATIONS_DIR
from src.shared.enums.job_status import JobStatus
from src.shared.errors.migration_error import MigrationError


def user_version(database_file: Path) -> int:
    with closing(sqlite3.connect(database_file)) as connection:
        return connection.execute("PRAGMA user_version").fetchone()[0]


def build_app(tmp_path: Path, database_file: Path, migrations_dir: Path):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    lifespan = migrate_on_startup(database_file, migrations_dir)
    return create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 18, tzinfo=UTC), lifespan=lifespan)


def test_startup_applies_pending_migrations(tmp_path: Path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001_create_items.sql").write_text("CREATE TABLE items (id INTEGER PRIMARY KEY);", encoding="utf-8")
    database_file = tmp_path / "data" / "app.db"
    app = build_app(tmp_path, database_file, migrations_dir)
    assert not database_file.exists()
    with TestClient(app):
        assert user_version(database_file) == 1


def test_startup_fails_fast_on_an_invalid_migration(tmp_path: Path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "init.sql").write_text("CREATE TABLE items (id INTEGER PRIMARY KEY);", encoding="utf-8")
    app = build_app(tmp_path, tmp_path / "app.db", migrations_dir)
    with pytest.raises(MigrationError), TestClient(app):
        pass


def test_default_app_migrates_the_configured_database_only_at_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_file = tmp_path / "data" / "app.db"
    monkeypatch.setenv("APP_STORAGE__DATABASE_FILE", str(database_file))
    app = build_default_app()
    assert not database_file.exists()
    with TestClient(app):
        assert database_file.is_file()


class RecordingWorker:
    def __init__(self, database_file: Path, job_id: str) -> None:
        self.database_file = database_file
        self.job_id = job_id
        self.status_at_start: str | None = None
        self.stopped = False

    def start(self) -> None:
        with closing(sqlite3.connect(self.database_file)) as connection:
            self.status_at_start = connection.execute("SELECT status FROM jobs WHERE id = ?", (self.job_id,)).fetchone()[0]

    def stop(self) -> None:
        self.stopped = True


def seed_interrupted_job(database_file: Path) -> str:
    open_jobs = open_job_transaction(database_file)
    with closing(open_database(database_file)) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
    job = NewJob(str(uuid.uuid4()), "v1", "pregunta", False, "k" * 64, JobStatus.QUEUED, "2026-10-18T11:00:00Z")
    with open_jobs() as jobs:
        jobs.add_document_version(NewDocumentVersion("d1", "v1", "ley.pdf", 1, "ley.pdf", "a" * 64, "a.pdf", "2026-10-18T11:00:00Z"))
        jobs.add_job(job)
        jobs.set_status(job.id, JobStatus.ANALYZING, "2026-10-18T11:00:00Z")
    return job.id


def test_startup_requeues_interrupted_jobs_before_starting_the_worker(tmp_path: Path):
    database_file = tmp_path / "app.db"
    job_id = seed_interrupted_job(database_file)
    worker = RecordingWorker(database_file, job_id)
    recover = partial(recover_interrupted_jobs, open_job_transaction(database_file), lambda: datetime(2026, 10, 18, tzinfo=UTC))
    lifespan = run_jobs_on_startup(database_file, MIGRATIONS_DIR, recover, worker)
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    app = create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 18, tzinfo=UTC), lifespan=lifespan)
    with TestClient(app):
        assert worker.status_at_start == JobStatus.QUEUED.value
        assert not worker.stopped
    assert worker.stopped


def test_startup_on_a_new_database_migrates_before_recovering(tmp_path: Path):
    database_file = tmp_path / "data" / "app.db"
    recover = partial(recover_interrupted_jobs, open_job_transaction(database_file), lambda: datetime(2026, 10, 18, tzinfo=UTC))
    worker = RecordingWorker(database_file, "ninguno")
    worker.start = lambda: None
    lifespan = run_jobs_on_startup(database_file, MIGRATIONS_DIR, recover, worker)
    app = build_app_with_lifespan(tmp_path, lifespan)
    with TestClient(app):
        assert user_version(database_file) >= 1
    assert worker.stopped


def build_app_with_lifespan(tmp_path: Path, lifespan):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    return create_app(settings, system_prompt="reglas", now=lambda: datetime(2026, 10, 18, tzinfo=UTC), lifespan=lifespan)
