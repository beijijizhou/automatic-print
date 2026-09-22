from dataclasses import replace

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QTabWidget, QWidget

from ..automation.providers.registry import ERP_PLATFORMS
from ..layout_engine import LayoutSettings
from ..ui.worker_bridge import BatchWorkerBridge
from ..ui.layout_values import settings_from_window
from .platform.actions import BatchActionsMixin
from .platform.generation import GenerationActionsMixin
from .platform.routes import RouteActionsMixin
from .platform.view.generation_page import build_accepted_page, build_batch_generation_page
from .local.actions import LocalActionsMixin
from .local.page import build_local_page
from .platform.view.pages import (
    build_production_page,
)
from .task.actions import ThreadActionsMixin
from .task.worker import AutomationWorker
from .shell import build_controls, build_layout


class AutomationDialog(
    RouteActionsMixin,
    GenerationActionsMixin,
    LocalActionsMixin,
    BatchActionsMixin,
    ThreadActionsMixin,
    QWidget,
):
    def __init__(
        self,
        parent=None,
        *,
        local_only: bool = True,
        platform_names: tuple[str, ...] | None = None,
        download_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.local_only = local_only
        self.download_only = download_only
        self.platform_names = platform_names or tuple(ERP_PLATFORMS)
        self.settings_host = parent
        self.setWindowTitle(
            "本地排版工作台"
            if local_only
            else f"{self.platform_names[0]} ERP 批次下载"
        )
        self.resize(940, 640)
        self.thread = None
        self.worker = None
        self.worker_bridge = BatchWorkerBridge(self)
        self.records = []
        self.pending_batch_plan = None
        self.pending_route_plan = None
        self.pending_default_multi_plan = None
        self.preferences = (
            parent.preferences if parent is not None and hasattr(parent, "preferences")
            else QSettings("AutomaticPrint", "AutomaticPrint")
        )
        self._connect_worker_bridge()
        self._build_controls()
        self._build_tabs()
        self._build_layout()
        self.platform.currentTextChanged.connect(self.platform_changed)
        self.main_tabs.currentChanged.connect(self.main_tab_changed)
        if hasattr(self, "batch_rule_summary"):
            self.show_platform_batch_rules(self.platform.currentData())
        if hasattr(self, "route_summary"):
            self.show_route_controls(self.platform.currentData())
        self.refresh_current_section()

    def _connect_worker_bridge(self) -> None:
        bridge = self.worker_bridge
        bridge.progress.connect(self.append_log)
        bridge.progress.connect(self.show_progress_message)
        bridge.batches_loaded.connect(self.batches_finished)
        bridge.status_loaded.connect(self.status_finished)
        bridge.plan_loaded.connect(self.generation_plan_finished)
        bridge.completed.connect(self.action_finished)
        bridge.failed.connect(self.failed)
        bridge.cancelled.connect(self.task_cancelled)

    def _build_controls(self) -> None:
        build_controls(self)

    def _build_tabs(self) -> None:
        self.main_tabs = QTabWidget()
        if self.download_only:
            self.main_tabs.addTab(
                build_production_page(self, self.output_row), "生产批次"
            )
            if len(self.platform_names) == 1 and self.platform_names[0] in ERP_PLATFORMS:
                self.main_tabs.addTab(
                    build_batch_generation_page(self, self.platform_names[0]),
                    "批次生成",
                )
            else:
                self.main_tabs.tabBar().hide()
            return
        self.main_tabs.addTab(build_local_page(self), "本地排版")
        self.main_tabs.addTab(build_accepted_page(self), "已接单")
        self.main_tabs.addTab(
            build_production_page(self, self.output_row), "生产批次"
        )
        if self.local_only:
            self.main_tabs.setTabVisible(1, False)
            self.main_tabs.setTabVisible(2, False)
            self.main_tabs.tabBar().hide()

    def _build_layout(self) -> None:
        build_layout(self)

    def platform_changed(self, name: str) -> None:
        self.pending_batch_plan = None
        self.pending_route_plan = None
        self.pending_default_multi_plan = None
        self.records = []
        self.table.setRowCount(0)
        self.summary.setText(f"尚未读取 {name} 已生成批次。")
        if self.download_only:
            self.refresh_current_section()
            return
        self.generate_rules_button.setEnabled(False)
        self.accepted_table.setRowCount(0)
        self.accepted_summary.setText(
            f"{name}：尚未读取待生产订单数量。"
        )
        self.show_platform_batch_rules(name)
        if hasattr(self, "route_summary"):
            self.show_route_controls(name)
        self.refresh_current_section()

    def main_tab_changed(self, _index: int) -> None:
        self.refresh_current_section()

    def refresh_current_section(self) -> None:
        if self.local_only:
            return
        if self.thread is not None:
            return
        if self.download_only:
            self.show_cached_batches()
            return
        if self.main_tabs.currentIndex() == 0:
            self.refresh_local_batches()
            return
        if self.main_tabs.currentIndex() == 2:
            self.show_cached_batches()
            return
        self.log.clear()
        self._start_worker(
            AutomationWorker("status", self.platform.currentData())
        )

    def refresh_batches(self) -> None:
        self._start_worker(
            AutomationWorker("list", self.platform.currentData())
        )

    def _current_layout_settings(self) -> LayoutSettings:
        window = self.settings_host or self.window()
        if window is None or not hasattr(window, "width"):
            settings = LayoutSettings(png_engine="libvips")
        else:
            settings = settings_from_window(window)
        platform = self.platform.currentData()
        return replace(settings, platform_name=platform)
