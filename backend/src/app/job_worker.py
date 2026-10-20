import logging
import threading
from collections.abc import Callable

from src.shared.constants.limits.jobs import WORKER_IDLE_SECONDS, WORKER_STOP_TIMEOUT_SECONDS

WORKER_THREAD_NAME = "job-worker"

logger = logging.getLogger(__name__)


class JobWorker:
    def __init__(self, process: Callable[[], bool], idle_seconds: float = WORKER_IDLE_SECONDS) -> None:
        self.process = process
        self.idle_seconds = idle_seconds
        self.wake_event = threading.Event()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        self.stop_event.clear()
        self.thread = threading.Thread(target=self.run, name=WORKER_THREAD_NAME, daemon=True)
        self.thread.start()

    def wake(self) -> None:
        self.wake_event.set()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake_event.set()
        if self.thread is not None:
            self.thread.join(timeout=WORKER_STOP_TIMEOUT_SECONDS)

    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.wake_event.clear()
            if not self.process_safely():
                self.wake_event.wait(self.idle_seconds)

    def process_safely(self) -> bool:
        try:
            return self.process()
        except Exception:
            logger.exception("Job worker iteration failed")
            return False
