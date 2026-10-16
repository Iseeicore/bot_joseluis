from src.shared.constants.texts.configuration import overlap_too_large_text


class InvalidChunkOverlapError(ValueError):
    def __init__(self, overlap: int, size: int) -> None:
        super().__init__(overlap_too_large_text(overlap, size))
        self.overlap = overlap
        self.size = size
