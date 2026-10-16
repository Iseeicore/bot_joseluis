from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from src.document_analysis.domain.models import ChunkNote
from src.shared.constants.regex.note_facts import FINGERPRINT_PATTERN
from src.shared.errors.invalid_fingerprint_error import InvalidFingerprintError

TEMPORARY_SUFFIX = ".tmp"
SHARD_LENGTH = 2


class StoredNote(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    index: int
    first_page: int
    last_page: int
    text: str
    unverified_facts: tuple[str, ...]


class JsonNotesStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, fingerprint: str) -> Path:
        if not FINGERPRINT_PATTERN.fullmatch(fingerprint):
            raise InvalidFingerprintError(fingerprint)
        return self.root / fingerprint[:SHARD_LENGTH] / f"{fingerprint}.json"

    def load(self, fingerprint: str) -> ChunkNote | None:
        path = self.path_for(fingerprint)
        if not path.is_file():
            return None
        try:
            stored = StoredNote.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError):
            return None
        return ChunkNote(**stored.model_dump())

    def save(self, fingerprint: str, note: ChunkNote) -> None:
        path = self.path_for(fingerprint)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(TEMPORARY_SUFFIX)
        temporary.write_text(StoredNote(**vars(note)).model_dump_json(), encoding="utf-8")
        temporary.replace(path)
