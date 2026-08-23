from __future__ import annotations

import threading
import time
from typing import cast
from unittest.mock import Mock

import pytest

from racevault.generation.models import GroundedAnswerRequest
from racevault.generation.service import (
    AnswerService,
    GenerationQueueFullError,
    QueuedAnswerService,
)


class BlockingService:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def status(self) -> Mock:
        return Mock()

    def answer(self, _: GroundedAnswerRequest) -> Mock:
        self.started.set()
        self.release.wait(timeout=5)
        return Mock()


def test_generation_queue_bounds_active_and_waiting_requests() -> None:
    blocking = BlockingService()
    service = QueuedAnswerService(
        cast(AnswerService, blocking), max_concurrency=1, queue_depth=1
    )
    request = GroundedAnswerRequest(query="test")
    first = threading.Thread(target=service.answer, args=(request,))
    second = threading.Thread(target=service.answer, args=(request,))
    first.start()
    assert blocking.started.wait(timeout=2)
    second.start()
    deadline = time.monotonic() + 2
    while service.state() != (1, 1) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert service.state() == (1, 1)

    with pytest.raises(GenerationQueueFullError):
        service.answer(request)

    blocking.release.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert not first.is_alive()
    assert not second.is_alive()
