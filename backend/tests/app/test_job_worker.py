import logging
import threading

import pytest

from src.app.job_worker import JobWorker

WAIT_SECONDS = 5


class FakeQueue:
    def __init__(self, pending: int, failures: int = 0) -> None:
        self.pending = pending
        self.failures = failures
        self.calls = 0
        self.idle = threading.Event()

    def process(self) -> bool:
        self.calls += 1
        if self.failures:
            self.failures -= 1
            raise ZeroDivisionError("fallo de prueba")
        if self.pending:
            self.pending -= 1
            return True
        self.idle.set()
        return False


def test_processes_every_queued_job_then_sleeps_until_woken():
    queue = FakeQueue(pending=2)
    worker = JobWorker(queue.process, idle_seconds=60)
    worker.start()
    assert queue.idle.wait(WAIT_SECONDS)
    assert queue.calls == 3
    queue.idle.clear()
    queue.pending = 1
    worker.wake()
    assert queue.idle.wait(WAIT_SECONDS)
    worker.stop()
    assert queue.calls == 5
    assert not worker.is_running()


def test_keeps_running_after_an_unexpected_error(caplog: pytest.LogCaptureFixture):
    queue = FakeQueue(pending=1, failures=1)
    worker = JobWorker(queue.process, idle_seconds=0.01)
    with caplog.at_level(logging.ERROR):
        worker.start()
        assert queue.idle.wait(WAIT_SECONDS)
        worker.stop()
    assert queue.pending == 0
    assert "fallo de prueba" in caplog.text


def test_stop_ends_the_thread_while_it_is_idle():
    queue = FakeQueue(pending=0)
    worker = JobWorker(queue.process, idle_seconds=60)
    worker.start()
    assert queue.idle.wait(WAIT_SECONDS)
    assert worker.is_running()
    worker.stop()
    assert not worker.is_running()


def test_stop_and_wake_without_start_are_harmless():
    worker = JobWorker(FakeQueue(pending=0).process, idle_seconds=60)
    worker.wake()
    worker.stop()
    assert not worker.is_running()
