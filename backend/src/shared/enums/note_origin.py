from enum import StrEnum


class NoteOrigin(StrEnum):
    REUSED = "reused"
    GENERATED = "generated"
    FAILED = "failed"
