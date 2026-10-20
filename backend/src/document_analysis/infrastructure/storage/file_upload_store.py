import hashlib
import tempfile
from pathlib import Path
from typing import BinaryIO

from src.document_analysis.domain.models import StoredUpload
from src.shared.constants.limits.jobs import UPLOAD_READ_BLOCK_BYTES
from src.shared.errors.empty_upload_error import EmptyUploadError

UPLOAD_SUFFIX = ".pdf"
TEMPORARY_SUFFIX = ".tmp"


def copy_hashing(source: BinaryIO, target: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: source.read(UPLOAD_READ_BLOCK_BYTES), b""):
        digest.update(block)
        target.write(block)
        size += len(block)
    return digest.hexdigest(), size


class FileUploadStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, content: BinaryIO) -> StoredUpload:
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=self.root, suffix=TEMPORARY_SUFFIX, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                sha256, size = copy_hashing(content, temporary)
            except BaseException:
                temporary.close()
                temporary_path.unlink(missing_ok=True)
                raise
        return self.keep(temporary_path, sha256, size)

    def keep(self, temporary_path: Path, sha256: str, size: int) -> StoredUpload:
        if size == 0:
            temporary_path.unlink()
            raise EmptyUploadError()
        stored = StoredUpload(sha256=sha256, file_path=f"{sha256}{UPLOAD_SUFFIX}", size_bytes=size)
        target = self.root / stored.file_path
        if target.exists():
            temporary_path.unlink()
            return stored
        temporary_path.replace(target)
        return stored

    def read(self, file_path: str) -> bytes:
        return (self.root / file_path).read_bytes()
