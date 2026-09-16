from __future__ import annotations
from PySide6.QtCore import QSettings, QThread, QTimer, Qt
from PySide6.QtWidgets import QLabel, QMainWindow
from ..branding import application_icon
from .generation_actions import GenerationActionsMixin
from .preferences import PreferencesMixin
from .preference_autosave import PreferenceAutosave
from .generation_preview import GenerationPreviewController
from .update_actions import UpdateActionsMixin
from .worker_bridge import MainWindowWorkerBridge
from .workbench import build_activity, build_home, build_settings
from ..controllers import LayoutGenerationController


class MainWindow(
    PreferencesMixin,
    GenerationActionsMixin,
    UpdateActionsMixin,
    QMainWindow,
):
    def __init__(self, preferences=None) -> None:
        super().__init__()
        self.setWindowTitle("本地排版工作台")
        self.setWindowIcon(application_icon())
        self.resize(1440, 900)
        self.thread: QThread | None = None
        self.worker = None
        self.worker_bridge = MainWindowWorkerBridge(self)
        self.layout_generation = LayoutGenerationController(self)
        self.update_thread: QThread | None = None
        self.update_worker = None
        self.update_is_silent = True
        self.started_at = None
        self.stage_started_at = None
        self.current_stage = ""
        self.current_count = 0
        self.current_total = 0
        self.active_png_compression = 1
        self.active_png_engine = "pillow"
        self.preferences = preferences if preferences is not None else QSettings("AutomaticPrint", "AutomaticPrint")
        self._connect_worker_bridge()
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.refresh_timing)
        build_settings(self)
        build_activity(self)
        build_home(self)
        from .workbench_style import apply_workbench_style
        apply_workbench_style(self)
        self.preference_autosave = PreferenceAutosave(self)
        self.generation_preview = GenerationPreviewController(self)
        for label in self.findChildren(QLabel):
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.startup_update_timer = QTimer(self)
        self.startup_update_timer.setSingleShot(True)
        self.startup_update_timer.timeout.connect(lambda: self.check_for_updates(True) if self.isVisible() else None)
        self.startup_update_timer.start(2500)
    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.layout_progress.connect(self.update_progress)
        bridge.layout_finished.connect(self.generation_finished)
        bridge.layout_failed.connect(self.generation_failed)
        bridge.layout_cancelled.connect(self.generation_cancelled)
        bridge.update_finished.connect(self.update_check_finished)
        bridge.update_failed.connect(self.update_check_failed)
        bridge.update_progress.connect(self.show_update_progress)
    def has_active_tasks(self) -> bool:
        from .developer_mode import developer_task_active
        return any((self.layout_generation.active, self.update_thread is not None,
                    self.automation_home.thread is not None, developer_task_active(self),
                    getattr(getattr(self, 'bulk_controller', None), 'thread', None) is not None))
    def closeEvent(self, event) -> None:
        from .immediate_exit import exit_now
        exit_now(self)
        event.accept()
