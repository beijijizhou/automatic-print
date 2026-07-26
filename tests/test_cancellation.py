from pathlib import Path

import pytest

from automatic_print.cancellation import Cancellation, TaskCancelled
from automatic_print.layout import LayoutSettings
from automatic_print.ui.workers import GenerateWorker


def test_cancellation_raises_after_request() -> None:
    cancellation = Cancellation()
    cancellation.check()
    cancellation.request()

    with pytest.raises(TaskCancelled):
        cancellation.check()


def test_generate_worker_reports_safe_cancellation(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "automatic_print.ui.workers.generate_layout",
        lambda *_args: {"finished": True},
    )
    worker = GenerateWorker(
        [],
        Path(tmp_path),
        Path(tmp_path),
        "job",
        LayoutSettings(),
    )
    cancelled = []
    finished = []
    worker.cancelled.connect(lambda: cancelled.append(True))
    worker.finished.connect(lambda *_args: finished.append(True))

    worker.request_cancel()
    worker.run()

    assert cancelled == [True]
    assert finished == []
