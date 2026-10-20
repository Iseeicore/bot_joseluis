from collections.abc import Callable

ProgressCallback = Callable[[int, int], None]


def ignore_progress(done: int, total: int) -> None:
    return None
