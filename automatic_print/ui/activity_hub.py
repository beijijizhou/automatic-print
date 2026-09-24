"""Shared live-task state for every top-level workbench tab."""

from dataclasses import dataclass
from time import monotonic

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QProgressBar


@dataclass
class Activity:
    key: str
    title: str
    message: str = "尚未开始"
    current_object: str = ""
    state: str = "idle"
    step: int = 0
    current: int | None = None
    total: int | None = None
    progress_text: str = ""
    started_at: float | None = None
    step_started_at: float | None = None
    updated_at: float = 0.0
    stop: object = None


class ActivityHub(QObject):
    changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records = {}
        self.current_key = ""

    def begin(self, key, title, message, *, stop=None, current_object=""):
        now = monotonic()
        record = self._record(key, title)
        record.title = title
        record.message = str(message)
        record.current_object = str(current_object)
        record.state = "running"
        record.step = 1
        record.current = record.total = None
        record.progress_text = ""
        record.started_at = record.step_started_at = record.updated_at = now
        record.stop = stop
        self.current_key = key
        self._emit()

    def update(
        self, key, *, title=None, message=None, current_object=None,
        current=None, total=None, progress_text=None, new_step=False,
    ):
        record = self._record(key, title or key)
        now = monotonic()
        if title is not None:
            record.title = str(title)
        if message is not None:
            record.message = str(message)
        if new_step:
            record.step += 1
            record.step_started_at = now
        if current_object is not None:
            record.current_object = str(current_object)
        if current is not None or total is not None:
            record.current, record.total = current, total
        if progress_text is not None:
            record.progress_text = str(progress_text)
        record.updated_at = now
        if record.state == "running":
            self.current_key = key
        self._emit()

    def finish(self, key, message, *, state="completed", current_object=None):
        record = self._record(key, key)
        record.message = str(message)
        record.state = state
        record.updated_at = monotonic()
        record.stop = None
        if current_object is not None:
            record.current_object = str(current_object)
        if state == "completed" and record.total:
            record.current = record.total
        self.current_key = key
        self._emit()

    def select(self, key):
        if key in self._records:
            self.current_key = key
            self._emit()

    def stop_current(self):
        record = self._records.get(self.current_key)
        if record is not None and callable(record.stop):
            record.stop()

    def snapshot(self):
        records = sorted(
            self._records.values(),
            key=lambda item: (item.state == "running", item.updated_at),
            reverse=True,
        )[:8]
        return {
            "current_key": self.current_key,
            "activities": [item.__dict__.copy() for item in records],
        }

    def _record(self, key, title):
        if key not in self._records:
            self._records[key] = Activity(str(key), str(title), updated_at=monotonic())
        return self._records[key]

    def _emit(self):
        self.changed.emit(self.snapshot())


class ActivityLabel(QLabel):
    """Compatibility label that mirrors legacy DTF status into the hub."""

    def __init__(self, text, hub, field, parent=None):
        self._activity_hub = hub
        self._activity_field = field
        super().__init__(text, parent)

    def setText(self, text):
        super().setText(text)
        value = str(text)
        if self._activity_field == "message":
            self._activity_hub.update("dtf-layout", title="DTF 排版", message=value)
        else:
            self._activity_hub.update(
                "dtf-layout", title="DTF 排版", current_object=value,
            )


class ActivityProgressBar(QProgressBar):
    def __init__(self, hub, parent=None):
        self._activity_hub = hub
        self._activity_current = 0
        self._activity_total = 100
        self._activity_format = ""
        super().__init__(parent)

    def setRange(self, minimum, maximum):
        super().setRange(minimum, maximum)
        self._activity_total = None if (minimum, maximum) == (0, 0) else maximum
        self._sync()

    def setValue(self, value):
        super().setValue(value)
        self._activity_current = value
        self._sync()

    def setFormat(self, text):
        super().setFormat(text)
        self._activity_format = str(text)
        self._sync()

    def _sync(self):
        hub = getattr(self, "_activity_hub", None)
        if hub is not None:
            hub.update(
                "dtf-layout", title="DTF 排版", current=self._activity_current,
                total=self._activity_total, progress_text=self._activity_format,
            )
