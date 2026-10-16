from pathlib import Path

import pytest

from src.document_analysis.domain.models import ChunkNote
from src.document_analysis.domain.ports import NotesStore
from src.document_analysis.infrastructure.storage.json_notes_store import JsonNotesStore
from src.shared.errors.invalid_fingerprint_error import InvalidFingerprintError

FINGERPRINT = "ab" * 32
NOTE = ChunkNote(index=3, first_page=10, last_page=12, text="- punto uno\n- punto dos", unverified_facts=("PEREZ", "99"))


def test_saved_note_is_loaded_back_identical(tmp_path: Path):
    store = JsonNotesStore(tmp_path)
    store.save(FINGERPRINT, NOTE)
    assert store.load(FINGERPRINT) == NOTE


def test_unknown_fingerprint_gives_none(tmp_path: Path):
    assert JsonNotesStore(tmp_path).load(FINGERPRINT) is None


def test_directory_is_created_on_first_save(tmp_path: Path):
    root = tmp_path / "nested" / "notes"
    JsonNotesStore(root).save(FINGERPRINT, NOTE)
    assert root.is_dir()


def test_corrupt_file_counts_as_missing(tmp_path: Path):
    store = JsonNotesStore(tmp_path)
    store.save(FINGERPRINT, NOTE)
    next(tmp_path.rglob("*.json")).write_text("{ not json", encoding="utf-8")
    assert store.load(FINGERPRINT) is None


def test_file_with_wrong_shape_counts_as_missing(tmp_path: Path):
    store = JsonNotesStore(tmp_path)
    store.save(FINGERPRINT, NOTE)
    next(tmp_path.rglob("*.json")).write_text('{"text": 5}', encoding="utf-8")
    assert store.load(FINGERPRINT) is None


def test_saving_again_replaces_and_leaves_no_temporary_files(tmp_path: Path):
    store = JsonNotesStore(tmp_path)
    store.save(FINGERPRINT, NOTE)
    newer = ChunkNote(index=0, first_page=1, last_page=1, text="- nuevo", unverified_facts=())
    store.save(FINGERPRINT, newer)
    assert store.load(FINGERPRINT) == newer
    assert [path.suffix for path in tmp_path.rglob("*") if path.is_file()] == [".json"]


@pytest.mark.parametrize("fingerprint", ["../escape", "a/b", "", "ZZ" * 32])
def test_fingerprint_that_could_escape_the_directory_is_rejected(tmp_path: Path, fingerprint: str):
    store = JsonNotesStore(tmp_path)
    with pytest.raises(InvalidFingerprintError):
        store.save(fingerprint, NOTE)
    with pytest.raises(InvalidFingerprintError):
        store.load(fingerprint)


def test_satisfies_the_notes_store_port(tmp_path: Path):
    assert isinstance(JsonNotesStore(tmp_path), NotesStore)
