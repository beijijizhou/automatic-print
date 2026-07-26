from __future__ import annotations

from threading import Event


class TaskCancelled(Exception):
    """Raised cooperatively when the user requests a safe stop."""


class Cancellation:
    def __init__(self) -> None:
        self._requested = Event()

    def request(self) -> None:
        self._requested.set()

    def check(self) -> None:
        if self._requested.is_set():
            raise TaskCancelled("用户已停止当前处理。")
