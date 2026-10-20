from src.shared.constants.texts.configuration import summary_batch_too_large_text


class SummaryBatchTooLargeError(ValueError):
    def __init__(self, batch_chars: int, limit: int) -> None:
        super().__init__(summary_batch_too_large_text(batch_chars, limit))
        self.batch_chars = batch_chars
        self.limit = limit
