"""Fixed workbench header for current task steps across every tab."""

from time import monotonic

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox, QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QVBoxLayout,
)

class GlobalActivityCenter(QGroupBox):
    def __init__(self, hub, parent=None):
        super().__init__("统一任务进度 · 切换任何页面都保持可见", parent)
        self.hub = hub
        self.snapshot = {"current_key": "", "activities": []}
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self._select)
        self.state = QLabel("空闲")
        self.state.setObjectName("globalActivityState")
        self.step = QLabel("当前没有运行中的任务")
        self.step.setWordWrap(True)
        self.step.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.details = QLabel("当前对象：— · 本步骤 0 秒 · 总计 0 秒")
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.stop = QPushButton("停止当前任务")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.hub.stop_current)
        header = QHBoxLayout()
        header.addWidget(QLabel("任务"))
        header.addWidget(self.selector, 1)
        header.addWidget(self.state)
        header.addWidget(self.stop)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.step)
        layout.addWidget(self.progress)
        layout.addWidget(self.details)
        self.timer = QTimer(self)
        self.timer.setInterval(1_000)
        self.timer.timeout.connect(self._render)
        self.timer.start()
        hub.changed.connect(self.apply_snapshot)
        self.apply_snapshot(hub.snapshot())

    def apply_snapshot(self, snapshot):
        self.snapshot = snapshot
        selected = snapshot.get("current_key") or self.selector.currentData()
        self.selector.blockSignals(True)
        self.selector.clear()
        for activity in snapshot.get("activities") or []:
            marker = "运行中" if activity["state"] == "running" else _state_text(activity["state"])
            self.selector.addItem(f"{activity['title']} · {marker}", activity["key"])
        index = self.selector.findData(selected)
        self.selector.setCurrentIndex(index if index >= 0 else 0)
        self.selector.blockSignals(False)
        self._render()

    def _select(self, _index):
        key = self.selector.currentData()
        if key:
            self.hub.select(key)

    def _render(self):
        key = self.selector.currentData() or self.snapshot.get("current_key")
        activity = next(
            (item for item in self.snapshot.get("activities") or [] if item["key"] == key),
            None,
        )
        if activity is None:
            self.state.setText("空闲")
            self.step.setText("当前没有运行中的任务")
            self.details.setText("当前对象：— · 本步骤 0 秒 · 总计 0 秒")
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.stop.setEnabled(False)
            return
        self.state.setText(_state_text(activity["state"]))
        number = f"步骤 {activity['step']} · " if activity["step"] else ""
        self.step.setText(number + activity["message"])
        current, total = activity["current"], activity["total"]
        if total in (None, 0):
            if activity["state"] == "running":
                self.progress.setRange(0, 0)
            else:
                self.progress.setRange(0, 1)
                self.progress.setValue(1 if activity["state"] == "completed" else 0)
        else:
            self.progress.setRange(0, int(total))
            self.progress.setValue(max(0, min(int(total), int(current or 0))))
            self.progress.setFormat(activity["progress_text"] or "%v / %m")
        now = monotonic()
        total_seconds = int(now - activity["started_at"]) if activity["started_at"] else 0
        step_seconds = int(now - activity["step_started_at"]) if activity["step_started_at"] else 0
        current_object = activity["current_object"] or "—"
        self.details.setText(
            f"当前对象：{current_object} · 本步骤 {step_seconds} 秒 · 总计 {total_seconds} 秒"
        )
        self.stop.setEnabled(activity["state"] == "running" and activity["stop"] is not None)


def _state_text(state):
    return {
        "running": "运行中", "completed": "已完成", "failed": "失败",
        "stopped": "已停止", "idle": "空闲",
    }.get(state, "未知")
