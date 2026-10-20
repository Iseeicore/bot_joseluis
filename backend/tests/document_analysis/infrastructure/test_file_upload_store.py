import hashlib
import io
from pathlib import Path

import pytest

from src.document_analysis.infrastructure.storage.file_upload_store import FileUploadStore
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.empty_upload_error import EmptyUploadError

CONTENT = b"%PDF-1.7 " + b"x" * 3_000_000


def test_saves_the_upload_under_its_sha256_and_reports_it(tmp_path: Path):
    store = FileUploadStore(tmp_path / "uploads")
    stored = store.save(io.BytesIO(CONTENT))
    sha256 = hashlib.sha256(CONTENT).hexdigest()
    assert stored.sha256 == sha256
    assert stored.file_path == f"{sha256}.pdf"
    assert stored.size_bytes == len(CONTENT)
    assert (tmp_path / "uploads" / f"{sha256}.pdf").read_bytes() == CONTENT
    assert store.read(stored.file_path) == CONTENT


def test_leaves_no_temporary_files_behind(tmp_path: Path):
    store = FileUploadStore(tmp_path)
    stored = store.save(io.BytesIO(CONTENT))
    assert [path.name for path in tmp_path.iterdir()] == [stored.file_path]


def test_same_content_is_stored_once_and_not_rewritten(tmp_path: Path):
    store = FileUploadStore(tmp_path)
    first = store.save(io.BytesIO(CONTENT))
    target = tmp_path / first.file_path
    modified = target.stat().st_mtime_ns
    second = store.save(io.BytesIO(CONTENT))
    assert second == first
    assert target.stat().st_mtime_ns == modified
    assert len(list(tmp_path.iterdir())) == 1


def test_rejects_an_empty_file_without_writing_anything(tmp_path: Path):
    store = FileUploadStore(tmp_path / "uploads")
    with pytest.raises(EmptyUploadError) as raised:
        store.save(io.BytesIO(b""))
    assert raised.value.status_code == 400
    assert raised.value.error_code is ErrorCode.EMPTY_FILE
    assert raised.value.message == "El archivo enviado está vacío."
    assert list((tmp_path / "uploads").iterdir()) == []


class BrokenStream(io.RawIOBase):
    def __init__(self) -> None:
        self.calls = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        self.calls += 1
        if self.calls > 1:
            raise OSError("conexion cortada")
        return b"%PDF parcial"


def test_failed_read_leaves_no_partial_file(tmp_path: Path):
    store = FileUploadStore(tmp_path)
    with pytest.raises(OSError):
        store.save(BrokenStream())
    assert list(tmp_path.iterdir()) == []
