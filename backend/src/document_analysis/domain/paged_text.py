from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class PagedText:
    text: str
    page_starts: tuple[int, ...]
    page_numbers: tuple[int, ...]

    def page_at(self, offset: int) -> int:
        index = max(bisect_right(self.page_starts, offset) - 1, 0)
        return self.page_numbers[index]
