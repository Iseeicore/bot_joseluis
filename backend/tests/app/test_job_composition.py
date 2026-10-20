from dataclasses import replace
from pathlib import Path

from src.app.generation_options import to_generation_options
from src.app.job_composition import build_job_identity, build_process_setup
from src.shared.config.settings import load_settings
from src.shared.constants.config import DEFAULT_CONFIG_FILE
from tests.document_analysis.job_fakes import MemoryJobRepository, MemoryUploadStore, fixed_clock


def test_job_identity_takes_the_summary_batch_size_from_the_summary_profile(tmp_path: Path):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    identity = build_job_identity(settings)
    assert identity.summary_batch_chars == settings.summary.summary_batch_chars
    assert identity.summary_options == to_generation_options(settings.summary)
    assert identity.notes_options == to_generation_options(settings.active)


def test_summary_batches_use_the_batch_size_of_the_job_identity(tmp_path: Path):
    settings = load_settings(DEFAULT_CONFIG_FILE, tmp_path / ".env")
    identity = replace(build_job_identity(settings), summary_batch_chars=1234)
    setup = build_process_setup(settings, MemoryJobRepository().transaction, MemoryUploadStore(), identity, fixed_clock)
    assert setup.summary.batch_chars == 1234
    assert setup.summary.options == identity.summary_options
